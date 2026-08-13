#!/usr/bin/env python3

import argparse
import fcntl
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


# LogLake 로그 최상위 폴더
LOG_ROOT = Path("/home/ec2-user/logs")

# rclone Google Drive remote 이름
RCLONE_REMOTE = "gdrive"

# Google Drive 저장 경로
DRIVE_ROOT = "MLOps 수업자료 모음/MLO-01-001-backup"

# ec2-user의 rclone 인증 설정
RCLONE_CONFIG = Path(
    "/home/ec2-user/.config/rclone/rclone.conf"
)

# 중복 실행 방지용 파일
LOCK_FILE = Path(
    "/home/ec2-user/scripts/state/upload_drive_force.lock"
)

KST = ZoneInfo("Asia/Seoul")


def parse_arguments():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--date",
        help="강제로 업로드할 날짜. 예: 26-08-13",
    )

    parser.add_argument(
        "--hour",
        help="강제로 업로드할 시간. 예: 10h",
    )

    parser.add_argument(
        "--offset-hours",
        type=int,
        default=0,
        help="현재 시간에서 몇 시간 전 폴더를 보낼지 지정",
    )

    return parser.parse_args()


def determine_target(args):
    # 날짜와 시간을 직접 지정한 경우
    if args.date and args.hour:
        return args.date, args.hour

    # 둘 중 하나만 입력한 것은 오류
    if args.date or args.hour:
        raise ValueError(
            "--date와 --hour는 반드시 함께 입력해야 합니다."
        )

    target_time = datetime.now(KST) - timedelta(
        hours=args.offset_hours
    )

    return (
        target_time.strftime("%y-%m-%d"),
        target_time.strftime("%Hh"),
    )


def find_rclone():
    rclone = shutil.which("rclone")

    if rclone is None:
        raise RuntimeError(
            "rclone 명령을 찾을 수 없습니다."
        )

    return rclone


def contains_file(directory):
    return any(
        path.is_file()
        for path in directory.rglob("*")
    )


def upload_directory(
    rclone,
    source_directory,
    destination,
):
    command = [
        rclone,
        "copy",
        str(source_directory),
        destination,
        "--config",
        str(RCLONE_CONFIG),
        "--checksum",
        "--retries",
        "3",
        "--low-level-retries",
        "10",
        "--transfers",
        "2",
        "--checkers",
        "4",
        "--stats-one-line",
        "--stats",
        "10s",
    ]

    print(
        f"[UPLOAD] {source_directory} -> {destination}",
        flush=True,
    )

    # 특정 폴더 전송 실패가 다른 로그 폴더의
    # 전송까지 막지 않도록 즉시 예외를 발생시키지 않음
    result = subprocess.run(command, check=False)

    return result.returncode


def main():
    args = parse_arguments()

    try:
        target_date, target_hour = determine_target(args)
        rclone = find_rclone()
    except (ValueError, RuntimeError) as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 1

    if not LOG_ROOT.is_dir():
        print(
            f"[ERROR] 로그 루트가 없습니다: {LOG_ROOT}",
            file=sys.stderr,
        )
        return 1

    if not RCLONE_CONFIG.is_file():
        print(
            f"[ERROR] rclone 설정이 없습니다: {RCLONE_CONFIG}",
            file=sys.stderr,
        )
        return 1

    LOCK_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with LOCK_FILE.open("w") as lock:
        try:
            # 10분 작업이 끝나지 않은 상태에서
            # 40분 작업이 중복 실행되는 것 방지
            fcntl.flock(
                lock.fileno(),
                fcntl.LOCK_EX | fcntl.LOCK_NB,
            )
        except BlockingIOError:
            print(
                "[SKIP] 이전 업로드가 아직 실행 중입니다."
            )
            return 0

        print(
            f"[START] 대상={target_date}/{target_hour}",
            flush=True,
        )

        # 구조:
        # logs/<분류>/<로그종류>/<날짜>/<시간>
        hour_directories = sorted(
            directory
            for directory in LOG_ROOT.glob(
                f"*/*/{target_date}/{target_hour}"
            )
            if directory.is_dir()
        )

        # 해당 시간 폴더가 아직 없어도 실패 처리하지 않음
        if not hour_directories:
            print(
                "[INFO] 해당 시간 폴더가 없습니다. "
                "업로드 없이 정상 종료합니다."
            )
            return 0

        upload_count = 0
        empty_count = 0
        failure_count = 0

        for source_directory in hour_directories:
            relative_parts = source_directory.relative_to(
                LOG_ROOT
            ).parts

            category = relative_parts[0]
            log_type = relative_parts[1]

            # 파일이 없는 로그 종류만 건너뜀
            # 다른 로그 종류의 업로드는 계속 진행됨
            if not contains_file(source_directory):
                empty_count += 1
                print(
                    f"[EMPTY] {source_directory}",
                    flush=True,
                )
                continue

            destination = (
                f"{RCLONE_REMOTE}:"
                f"{DRIVE_ROOT}/"
                f"{target_date}/"
                f"{target_hour}/"
                f"{category}/"
                f"{log_type}"
            )

            return_code = upload_directory(
                rclone,
                source_directory,
                destination,
            )

            if return_code == 0:
                upload_count += 1
            else:
                failure_count += 1
                print(
                    f"[FAILED] {source_directory}, "
                    f"return_code={return_code}",
                    file=sys.stderr,
                    flush=True,
                )

        print(
            "[FINISH] "
            f"성공={upload_count}, "
            f"빈 폴더={empty_count}, "
            f"실패={failure_count}",
            flush=True,
        )

        # 일부 로그 종류가 실패해도 나머지는 이미 전송됨
        # cron에서는 실패 기록을 남기고 40분에 다시 시도
        return 1 if failure_count else 0


if __name__ == "__main__":
    sys.exit(main())
# Google Drive 로그 업로드 코드 인수인계서

## 1. 코드 목적

이 Python 스크립트는 지정한 날짜·시간의 로그 폴더를 찾아 `rclone copy`로 Google Drive에 업로드한다.

핵심 동작은 다음과 같다.

1. 업로드할 날짜와 시간을 결정한다.
2. `logs/<분류>/<로그종류>/<날짜>/<시간>` 폴더를 찾는다.
3. 파일이 있는 폴더만 Google Drive에 업로드한다.
4. 한 폴더가 실패해도 다음 폴더를 계속 처리한다.
5. 파일 잠금으로 동일 EC2의 중복 실행을 막는다.

> 현재 코드는 로그 업로드 전용이다. MySQL·MongoDB dump 생성이나 DB 복구는 수행하지 않는다.

## 2. 입출력 규칙

### 실행 인수

| 인수 | 설명 | 예시 |
|---|---|---|
| `--date` | 직접 지정할 날짜 | `--date 26-08-13` |
| `--hour` | 직접 지정할 시간 | `--hour 10h` |
| `--offset-hours` | 현재 KST에서 몇 시간 전을 선택할지 지정 | `--offset-hours 1` |

`--date`와 `--hour`는 반드시 함께 사용한다. 두 값이 모두 있으면 `--offset-hours`는 무시된다.

```bash
# 현재 시간 폴더
python3 upload_drive_force.py

# 직전 시간 폴더
python3 upload_drive_force.py --offset-hours 1

# 특정 시간 폴더
python3 upload_drive_force.py --date 26-08-13 --hour 10h
```

### 종료 코드

| 코드 | 의미 |
|---:|---|
| `0` | 업로드 성공, 대상 없음, 빈 폴더 또는 중복 실행 감지 |
| `1` | 인수 오류, 필수 경로·명령 누락 또는 하나 이상의 업로드 실패 |

대상 폴더가 없거나 비어 있어도 `0`을 반환한다. 따라서 호출 측에서는 종료 코드뿐 아니라 `[INFO]`, `[EMPTY]`, `[FINISH]` 메시지도 확인해야 한다.

## 3. 경로 변환

### 로컬 경로

```text
/home/ec2-user/logs/<분류>/<로그종류>/<YY-MM-DD>/<HHh>/
```

실제 검색 패턴은 다음과 같다.

```python
LOG_ROOT.glob(f"*/*/{target_date}/{target_hour}")
```

`LOG_ROOT` 아래에 `<분류>`와 `<로그종류>`라는 정확히 두 단계가 있어야 한다. 중간 단계가 추가되면 검색되지 않는다.

### Google Drive 경로

```text
gdrive:MLOps 수업자료 모음/MLO-01-001-backup/
└── <YY-MM-DD>/<HHh>/<분류>/<로그종류>/
```

예시:

```text
로컬  /home/ec2-user/logs/car/crawling/26-08-13/10h/app.log
Drive gdrive:MLOps 수업자료 모음/MLO-01-001-backup/26-08-13/10h/car/crawling/app.log
```

## 4. 전역 상수

| 상수 | 역할 |
|---|---|
| `LOG_ROOT` | 로컬 로그 최상위 경로 |
| `RCLONE_REMOTE` | rclone Google Drive remote 이름 |
| `DRIVE_ROOT` | remote 내부 백업 경로 |
| `RCLONE_CONFIG` | rclone 인증 설정 파일 |
| `LOCK_FILE` | 중복 실행 방지 잠금 파일 |
| `KST` | 날짜·시간 계산 기준 |

경로를 바꿀 때는 함수 내부보다 이 상수를 우선 수정한다.

## 5. 함수별 역할

### `parse_arguments()`

세 개의 CLI 인수를 파싱하여 `argparse.Namespace`를 반환한다.

```text
args.date
args.hour
args.offset_hours
```

현재 날짜·시간 문자열의 형식은 검증하지 않는다. `--date abc --hour xyz`도 파싱 단계에서는 통과한다.

### `determine_target(args)`

업로드 대상 `(target_date, target_hour)`를 반환한다.

```text
date와 hour 모두 있음
→ 입력값 그대로 반환

둘 중 하나만 있음
→ ValueError

둘 다 없음
→ 현재 KST - offset_hours
→ %y-%m-%d, %Hh 형식으로 반환
```

예를 들어 KST `2026-08-13 10:30`에 `--offset-hours 1`을 사용하면 `("26-08-13", "09h")`를 반환한다.

### `find_rclone()`

```python
shutil.which("rclone")
```

현재 프로세스의 `PATH`에서 rclone을 찾는다. 찾지 못하면 `RuntimeError`가 발생한다. cron의 PATH는 로그인 셸과 다를 수 있다는 점에 주의한다.

### `contains_file(directory)`

```python
any(path.is_file() for path in directory.rglob("*"))
```

대상 폴더와 모든 하위 폴더에서 파일이 하나라도 발견되면 `True`를 반환한다. 파일이 없으면 rclone을 실행하지 않는다.

### `upload_directory(rclone, source_directory, destination)`

한 개의 로그 종류 폴더를 Google Drive에 전송한다.

명령을 문자열이 아닌 인수 리스트로 구성하므로 공백이 포함된 Drive 경로도 하나의 인수로 전달된다. `shell=True`를 사용하지 않는다.

| rclone 옵션 | 의미 |
|---|---|
| `copy` | 파일을 복사하며 원격의 추가 파일은 삭제하지 않음 |
| `--checksum` | 가능한 경우 checksum으로 동일 파일 판단 |
| `--retries 3` | 전체 작업 재시도 |
| `--low-level-retries 10` | API 요청 등 저수준 재시도 |
| `--transfers 2` | 동시 전송 수 2개 |
| `--checkers 4` | 동시 검사 수 4개 |
| `--stats 10s` | 10초마다 통계 출력 |

```python
result = subprocess.run(command, check=False)
return result.returncode
```

`check=False`이므로 rclone 실패가 즉시 Python 예외가 되지 않는다. return code만 호출자에게 전달하여 다른 폴더의 처리를 계속할 수 있다.

### `main()`

전체 실행 순서는 다음과 같다.

1. 인수를 파싱한다.
2. 날짜·시간과 rclone 경로를 결정한다.
3. 로그 루트와 rclone 설정 파일을 검사한다.
4. 잠금 파일 상위 폴더를 생성한다.
5. non-blocking exclusive lock을 획득한다.
6. 대상 시간 폴더들을 정렬한다.
7. 빈 폴더를 제외하고 폴더별 업로드를 실행한다.
8. 성공·빈 폴더·실패 건수를 출력한다.
9. 실패 건수에 따라 `0` 또는 `1`을 반환한다.

마지막의 `sys.exit(main())`이 `main()`의 반환값을 프로세스 종료 코드로 전달한다.

## 6. 중복 실행 방지

```python
fcntl.flock(
    lock.fileno(),
    fcntl.LOCK_EX | fcntl.LOCK_NB,
)
```

- `LOCK_EX`: 한 프로세스만 배타 잠금을 보유한다.
- `LOCK_NB`: 잠금이 이미 있으면 기다리지 않고 `BlockingIOError`를 발생시킨다.
- `with` 블록이 끝나면 파일 descriptor가 닫히면서 잠금이 해제된다.
- 잠금 파일이 디스크에 남아 있어도 실행 프로세스가 없으면 잠긴 상태가 아니다.

이 방식은 동일 EC2의 중복 실행만 방지한다. 여러 서버에서 실행하면 각 서버가 별도의 잠금을 얻을 수 있다.

## 7. 폴더별 처리 로직

예를 들어 대상 폴더가 다음과 같다고 가정한다.

```text
/home/ec2-user/logs/faq/db_load/26-08-13/10h
```

```python
relative_parts = source_directory.relative_to(LOG_ROOT).parts
```

결과:

```python
("faq", "db_load", "26-08-13", "10h")
```

Drive 경로에 사용할 값은 다음 두 개다.

```python
category = relative_parts[0]  # faq
log_type = relative_parts[1]  # db_load
```

각 폴더의 rclone return code가 `0`이면 성공 건수를, 아니면 실패 건수를 증가시킨다. 실패해도 `break`나 예외를 발생시키지 않으므로 다음 폴더를 계속 처리한다.

## 8. 로그 메시지

| 접두어 | 의미 |
|---|---|
| `[START]` | 대상 날짜·시간 처리 시작 |
| `[UPLOAD]` | rclone 실행 직전 원본·대상 출력 |
| `[EMPTY]` | 파일이 없는 폴더 건너뜀 |
| `[FAILED]` | 해당 폴더의 rclone 실패 |
| `[INFO]` | 대상 시간 폴더가 없음 |
| `[SKIP]` | 이전 실행이 잠금을 보유 중 |
| `[ERROR]` | 인수·명령·필수 경로 오류 |
| `[FINISH]` | 전체 처리 건수 요약 |

`[FAILED]`와 `[ERROR]`는 `stderr`로 출력하며 나머지는 주로 `stdout`으로 출력한다.

## 9. 예외 처리 범위

현재 명시적으로 처리하는 예외는 다음 두 개다.

```python
except (ValueError, RuntimeError) as error:
```

- `ValueError`: `--date`와 `--hour` 중 하나만 입력
- `RuntimeError`: rclone 실행 파일을 찾지 못함

다음 문제는 별도 처리되지 않아 traceback으로 종료될 수 있다.

- 잠금 디렉터리 생성·파일 열기 권한 오류
- 로그 폴더 탐색 중 파일시스템 오류
- `subprocess.run()` 실행 자체의 `OSError`
- rclone 프로세스가 응답하지 않는 상황

## 10. 코드 변경 시 주의사항

### 로그 폴더 구조 변경

다음 세 부분을 함께 수정해야 한다.

1. `LOG_ROOT.glob()` 패턴
2. `relative_parts`의 `category`, `log_type` 인덱스
3. Google Drive `destination` 조합

### `copy`를 `sync`로 변경

`sync`는 원격에만 존재하는 파일을 삭제할 수 있다. 백업 보존 방식이 달라지므로 단순 교체하면 안 된다.

### 병렬 처리 추가

현재 폴더들은 순차 처리되며 각 rclone 프로세스 내부에서만 `--transfers 2`가 적용된다. Python 레벨 병렬화를 추가하면 카운터 동시성, 로그 혼합, 네트워크 사용량과 API 제한을 함께 처리해야 한다.

### 잠금 방식 변경

모든 cron 실행이 동일한 `LOCK_FILE`을 사용해야 중복 실행을 막을 수 있다. 다중 서버로 확장할 때는 로컬 `flock`이 아니라 분산 leader lock이 필요하다.

## 11. 알려진 코드 한계

| ID | 한계 | 영향 |
|---|---|---|
| `CODE-LIM-001` | 날짜·시간 형식 검증 없음 | 잘못된 입력을 대상 없음으로 오인 가능 |
| `CODE-LIM-002` | 음수 offset 허용 | 미래 시간 폴더 검색 가능 |
| `CODE-LIM-003` | subprocess timeout 없음 | rclone 정지 시 잠금 장기 유지 가능 |
| `CODE-LIM-004` | 기록 중인 파일 확인 없음 | 불완전한 현재 시간 로그 업로드 가능 |
| `CODE-LIM-005` | 대상 없음·빈 폴더를 성공 처리 | 로그 생성 누락을 정상으로 오인 가능 |
| `CODE-LIM-006` | 로컬 잠금만 사용 | 다중 서버 중복 실행 방지 불가 |
| `CODE-LIM-007` | 업로드 manifest 없음 | 파일 단위 감사와 검증이 어려움 |
| `CODE-LIM-008` | DB dump 생성 없음 | 이 코드만으로 DB 백업·복구 불가 |

## 12. 권장 테스트

| 테스트 | 조건 | 기대 결과 |
|---|---|---|
| 직접 날짜 지정 | date·hour 모두 입력 | 입력값 튜플 반환 |
| date만 입력 | hour 없음 | `ValueError` |
| hour만 입력 | date 없음 | `ValueError` |
| offset 계산 | 고정 KST 시간, offset 1 | 한 시간 전 값 반환 |
| 자정 경계 | 00시, offset 1 | 전날 23시 반환 |
| rclone 없음 | PATH에서 미발견 | `RuntimeError` |
| 빈 폴더 | 하위 파일 없음 | `contains_file() == False` |
| 중첩 파일 | 하위 폴더에 파일 존재 | `contains_file() == True` |
| 일부 업로드 실패 | 한 폴더 return code 비정상 | 다음 폴더 계속 처리, 최종 exit 1 |
| 대상 폴더 없음 | glob 결과 없음 | `[INFO]`, exit 0 |
| 중복 실행 | 잠금 선점 | `[SKIP]`, exit 0 |

테스트에서는 `datetime.now`, `shutil.which`, `subprocess.run`과 파일 경로를 mock 또는 임시 디렉터리로 대체하는 것이 좋다.

## 13. 인수인계 핵심 요약

- 실행 진입점은 `main()`이다.
- 날짜·시간 결정은 `determine_target()`이 담당한다.
- 외부 업로드는 `upload_directory()`의 rclone subprocess가 담당한다.
- `check=False`와 return code 집계가 부분 실패 후 계속 처리되는 핵심이다.
- `fcntl.flock()`은 동일 EC2의 cron 중복 실행만 막는다.
- 경로 구조를 변경하면 glob, `relative_parts`, destination을 함께 수정해야 한다.
- 현재 코드는 로그만 업로드하며 DB 백업 코드는 포함하지 않는다.

# Crontab 설정·기준 및 연결 인수인계서

## 1. 목적

LogLake의 날짜·시간별 로그를 Google Drive로 자동 업로드하기 위한 Python 프로그램과 crontab 운영 방법을 기록한다.

## 2. 주요 경로

| 항목 | 경로 또는 값 |
|---|---|
| Python 업로더 | `/home/ec2-user/scripts/upload_drive_force.py` |
| LogLake 루트 | `/home/ec2-user/logs` |
| cron 로그 | `/home/ec2-user/scripts/run-logs/drive-cron.log` |
| 잠금 파일 디렉터리 | `/home/ec2-user/scripts/state` |
| rclone remote | `gdrive:` |
| Drive 루트 | `MLOps 수업자료 모음/MLO-01-001-backup` |

## 3. 디렉터리 매핑

원본:

```text
/home/ec2-user/logs/<분류>/<로그종류>/<YY-MM-DD>/<HHh>/
```

Drive:

```text
MLO-01-001-backup/<YY-MM-DD>/<HHh>/<분류>/<로그종류>/
```

## 4. 자동화 정책

```text
정시: LogLake 현재 시간 폴더에 로그 적재
10분: 현재 시간 폴더의 파일 1차 업로드
40분: 같은 시간 폴더 재확인 및 추가 업로드
```

현재 적재 정책에서는 `--offset-hours 0`을 사용한다. 원본 정책이 이전 시간 폴더 적재 방식으로 바뀌는 경우에만 `--offset-hours 1`로 변경한다.

## 5. Python 프로그램 동작

1. `Asia/Seoul` 기준 대상 날짜와 시간을 계산한다.
2. `/home/ec2-user/logs/*/*/<날짜>/<시간>` 경로를 탐색한다.
3. 파일이 없는 폴더는 `EMPTY`로 기록하고 다음 폴더를 처리한다.
4. 파일이 있는 폴더만 `rclone copy`로 업로드한다.
5. 로그 종류별 성공·실패를 집계한다.
6. 잠금 파일로 중복 실행을 방지한다.

`rclone sync`를 사용하면 원격 파일이 삭제될 수 있으므로 현재 목적에는 `copy`를 유지한다.

## 6. systemd timer 중지

cron과 기존 timer가 동시에 실행되지 않도록 한다.

```bash
sudo systemctl disable --now loglake-drive-upload.timer
systemctl is-active loglake-drive-upload.timer
```

정상 결과:

```text
inactive
```

## 7. crond 설정

```bash
sudo systemctl enable --now crond
sudo systemctl is-active crond
```

정상 결과:

```text
active
```

`ec2-user`로 등록한다.

```bash
whoami
crontab -e
```

최종 설정:

```cron
SHELL=/bin/bash
HOME=/home/ec2-user
PATH=/usr/local/bin:/usr/bin:/bin
TZ=Asia/Seoul

10,40 * * * * /usr/bin/python3 /home/ec2-user/scripts/upload_drive_force.py --offset-hours 0 >> /home/ec2-user/scripts/run-logs/drive-cron.log 2>&1
```

`sudo crontab -e`를 사용하면 root의 rclone 설정을 읽게 될 수 있으므로 사용하지 않는다.

## 8. 수동 검증

현재 시간 폴더 실행:

```bash
/usr/bin/python3 /home/ec2-user/scripts/upload_drive_force.py --offset-hours 0
```

특정 날짜·시간 실행:

```bash
/usr/bin/python3 /home/ec2-user/scripts/upload_drive_force.py \
  --date 26-08-13 \
  --hour 15h
```

## 9. cron 검증

```bash
crontab -l | nl -ba
crontab -l | sed -n 'l'
tail -100 /home/ec2-user/scripts/run-logs/drive-cron.log
sudo journalctl -u crond --since "2 hours ago" --no-pager
```

`RELOAD (/var/spool/cron/ec2-user)`는 설정을 다시 읽었다는 뜻일 뿐 업로드 성공을 의미하지 않는다. 성공 여부는 `drive-cron.log`에서 확인한다.

## 10. 발생 이슈와 대응

### 10.1 파일명과 옵션 사이 공백 누락

잘못된 명령:

```text
upload_drive_force.py--offset-hours 0
```

정상 명령:

```text
upload_drive_force.py --offset-hours 0
```

오류가 매분 반복되면 테스트용 `* * * * *` 줄이나 중복된 cron 줄이 남아 있는지 확인한다.

### 10.2 환경 파일 명령 오류

증상:

```text
loglake-drive.env: command not found
```

환경 파일을 단독 명령으로 등록한 것이 원인이다. 필요 없는 줄은 제거하고, 반드시 필요한 경우에만 절대경로를 `source`한다.

```bash
source /home/ec2-user/scripts/loglake-drive.env
```

### 10.3 일부 로그 누락

모든 파일이 있어야 전송하도록 검사하면 일부 파일 누락이 전체 업로드를 막는다. 최종 프로그램은 존재하는 파일만 전송하고 40분에 다시 확인한다.

## 11. 정상 판정 기준

| 로그 | 의미 |
|---|---|
| `[FINISH] 성공=N, 실패=0` | 정상 완료 |
| `해당 시간 폴더가 없습니다` | cron 정상, 원본 폴더 없음 |
| `rclone 설정이 없습니다` | 실행 사용자 또는 설정 경로 오류 |
| `rclone 명령을 찾을 수 없습니다` | PATH 또는 설치 경로 오류 |
| `[SKIP] 이전 업로드가 아직 실행 중` | 중복 실행 방지 정상 동작 |

## 12. 운영 체크리스트

- [ ] `crond` active 확인
- [ ] ec2-user crontab 확인
- [ ] `10,40` 등록 항목 하나만 존재
- [ ] 테스트용 매분 cron 제거
- [ ] 기존 systemd timer inactive 확인
- [ ] 수동 Python 실행 성공
- [ ] `drive-cron.log`의 실패 수 확인


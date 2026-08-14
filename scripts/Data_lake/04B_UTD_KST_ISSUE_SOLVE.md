# 서버시간과 한국시간 차이 적재 오류 해결 인수인계서

## 1. 목적

원본 서버, LogLake EC2, Python 업로더 및 crontab 사이의 시간대를 통일하여 날짜·시간 폴더 불일치로 발생하는 업로드 누락을 방지한다.

## 2. 발생 현상

초기 EC2는 UTC를 사용했고 Python은 `Asia/Seoul`을 사용했다. 두 시간대는 9시간 차이가 발생한다.

```text
EC2 UTC:  2026-08-12 15:00
한국 KST: 2026-08-13 00:00
```

동일한 순간에 다음과 같은 서로 다른 경로가 사용됐다.

```text
LogLake 실제 폴더: 26-08-12/15h
Python 검색 폴더:  26-08-13/00h
```

결과적으로 cron은 정상 실행돼도 Python이 실제 로그가 없는 폴더를 검색했다.

```text
[INFO] 해당 시간 폴더가 없습니다.
```

## 3. 원인

| 구성요소 | 기존 기준 |
|---|---|
| 원본 로그 서버 | UTC 또는 서버 기본시간 |
| LogLake 폴더 생성 | EC2 시스템 시간 |
| Python 업로더 | Asia/Seoul |
| cron 예약 | 서버 또는 cron 환경 시간 |

로그 경로에 날짜와 시간이 포함되므로 시간대 차이는 화면 표시 문제가 아니라 실제 경로 불일치로 이어졌다.

## 4. 최종 해결 기준

```text
원본 로그 서버 → Asia/Seoul
LogLake EC2   → Asia/Seoul
Python        → Asia/Seoul
crontab       → Asia/Seoul
```

## 5. 서버 시간대 설정

현재 설정 확인:

```bash
date
timedatectl
```

시간대 변경:

```bash
sudo timedatectl set-timezone Asia/Seoul
```

변경 확인:

```bash
timedatectl | grep "Time zone"
```

정상 결과:

```text
Time zone: Asia/Seoul (KST, +0900)
```

모든 로그 생성 서버와 LogLake 서버에서 동일하게 확인해야 한다.

## 6. Python 시간대 설정

`upload_drive_force.py`에서 다음 기준을 사용한다.

```python
from zoneinfo import ZoneInfo

SERVER_TZ = ZoneInfo("Asia/Seoul")
```

시간 계산:

```python
target_time = datetime.now(SERVER_TZ) - timedelta(
    hours=args.offset_hours
)
```

현재 시간 폴더를 업로드하므로 다음 옵션을 사용한다.

```bash
--offset-hours 0
```

## 7. crontab 시간대 설정

```cron
SHELL=/bin/bash
HOME=/home/ec2-user
PATH=/usr/local/bin:/usr/bin:/bin
TZ=Asia/Seoul

10,40 * * * * /usr/bin/python3 /home/ec2-user/scripts/upload_drive_force.py --offset-hours 0 >> /home/ec2-user/scripts/run-logs/drive-cron.log 2>&1
```

서버 자체가 서울 시간이더라도 cron 실행 환경을 명확하게 하기 위해 `TZ=Asia/Seoul`을 기록한다.

## 8. 시간 및 폴더 검증

현재 날짜·시간 폴더 값 확인:

```bash
CURRENT_DATE=$(date '+%y-%m-%d')
CURRENT_HOUR=$(date '+%Hh')
echo "${CURRENT_DATE}/${CURRENT_HOUR}"
```

현재 시간 로그 확인:

```bash
find /home/ec2-user/logs \
  -path "*/${CURRENT_DATE}/${CURRENT_HOUR}/*" \
  -type f
```

Python 계산 결과 확인:

```bash
/usr/bin/python3 /home/ec2-user/scripts/upload_drive_force.py --offset-hours 0
```

현재가 한국시간 15시라면 다음과 같이 출력되어야 한다.

```text
[START] 대상=26-08-13/15h
```

## 9. 최종 운영 흐름

```text
한국시간 15:00 → LogLake의 26-08-13/15h에 로그 적재
한국시간 15:10 → 26-08-13/15h Drive 1차 업로드
한국시간 15:40 → 26-08-13/15h 재확인 및 추가 업로드
```

## 10. 기존 UTC 폴더 처리

시간대 변경 전 생성된 UTC 기준 폴더명은 자동으로 변경되지 않는다. 기존 자료는 날짜와 시간을 직접 지정해 업로드한다.

```bash
/usr/bin/python3 /home/ec2-user/scripts/upload_drive_force.py \
  --date 26-08-12 \
  --hour 15h
```

UTC 기존 자료와 KST 신규 자료의 경로를 혼합하지 않도록 과거 데이터 정리 시 변환 기준을 기록한다.

## 11. 재발 방지

- 신규 EC2 생성 직후 `timedatectl` 확인
- 원본 서버와 LogLake 서버의 시간대 비교
- Bash `date`, Python `ZoneInfo`, cron `TZ`를 동일하게 유지
- 자정 전후 로그 적재와 업로드 테스트 수행
- 로그 적재 정책 변경 시 `--offset-hours`도 함께 검토

## 12. 인수인계 체크리스트

- [ ] 모든 EC2가 `Asia/Seoul` 사용
- [ ] Python이 `ZoneInfo("Asia/Seoul")` 사용
- [ ] crontab에 `TZ=Asia/Seoul` 설정
- [ ] LogLake 현재 시간 폴더와 서버 시간이 일치
- [ ] Python `[START] 대상`이 실제 폴더와 일치
- [ ] Google Drive 날짜·시간 폴더가 LogLake와 일치
- [ ] 자정 전후 날짜 전환 테스트 완료


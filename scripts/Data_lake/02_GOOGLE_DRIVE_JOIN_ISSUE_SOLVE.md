# Google Drive 연결 이슈 및 해결 인수인계서

## 1. 목적

EC2와 Google Drive 연결 과정에서 실제 발생한 오류, 원인, 해결 방법 및 재발 시 확인 절차를 기록한다.

## 2. 이슈별 대응

### 이슈 1. `gdrive` remote를 찾지 못함

증상:

```text
Failed to create file system for "gdrive:":
didn't find section in config file ("gdrive")
```

원인:

- remote 생성 후 최종 저장하지 않음
- `Gdrive` 등 다른 이름이나 대소문자로 저장
- 설정 사용자와 실행 사용자가 다름
- `sudo rclone`으로 root의 설정 파일을 참조

대응:

```bash
whoami
rclone listremotes
rclone config file
```

정상 기준:

```text
사용자: ec2-user
remote: gdrive:
설정: /home/ec2-user/.config/rclone/rclone.conf
```

remote 이름이 다르면 `rclone config`에서 이름을 수정하거나 다시 생성한다.

### 이슈 2. `config_token>` 입력 요구

원인:

브라우저가 없는 EC2에서 OAuth 인증을 직접 완료할 수 없다.

대응:

1. 개인 PC에서 rclone을 명령줄로 실행한다.
2. EC2가 표시한 `rclone authorize` 명령을 PC에서 실행한다.
3. Google 계정 로그인과 Drive 권한 승인을 완료한다.
4. 출력된 인증 결과를 EC2의 `config_token>`에 붙여 넣는다.

토큰 내용은 다른 사람에게 공유하지 않는다.

### 이슈 3. Windows에서 rclone을 더블클릭함

증상:

```text
This is a command line tool.
You need to open cmd.exe and run it from there.
```

원인:

rclone은 GUI 프로그램이 아닌 명령줄 프로그램이다.

대응:

```powershell
cd "$HOME\Downloads\rclone-v1.75.0-windows-amd64"
.\rclone.exe version
```

PowerShell 또는 CMD에서 `rclone authorize`를 실행한다.

### 이슈 4. Drive `directory not found`

증상:

```text
Failed to lsf: error in ListJSON: directory not found
```

원인:

- 조회 대상 날짜·시간 폴더가 Drive에 아직 없음
- LogLake에 원본 파일이 없어 업로드가 수행되지 않음
- 잘못된 날짜나 시간을 직접 입력함

확인:

```bash
find /home/ec2-user/logs -type f | head -30
```

실제 존재하는 날짜와 시간을 지정해 업로드한다.

```bash
/usr/bin/python3 /home/ec2-user/scripts/upload_drive_force.py \
  --date 26-08-13 \
  --hour 15h
```

Drive 조회:

```bash
rclone lsf \
  "gdrive:MLOps 수업자료 모음/MLO-01-001-backup/26-08-13/15h" \
  --recursive
```

### 이슈 5. Shared Client 사용 여부

rclone 공용 클라이언트는 실습에 사용할 수 있지만 지속 운영 시 사용량 제한 또는 공용 클라이언트 중단 영향을 받을 수 있다.

대응:

- 지속 운영 시 Google Cloud에서 생성한 전용 OAuth 클라이언트 사용
- 클라이언트 ID와 보안 비밀은 별도 보안 저장

### 이슈 6. OAuth 테스트 모드

원인:

OAuth 앱이 테스트 상태인 경우 정책과 구성에 따라 refresh token이 짧은 기간 후 만료될 수 있다.

대응:

- 사용할 계정을 테스트 사용자로 등록
- 운영 전 Google 인증 플랫폼의 게시 상태 확인
- 토큰 만료 시 rclone 재인증 수행

```bash
rclone config reconnect gdrive:
```

### 이슈 7. SSH 개인 키 권한 오류

증상:

```text
WARNING: UNPROTECTED PRIVATE KEY FILE!
Load key: bad permissions
```

원인:

SSH 개인 키 권한이 `0755`여서 다른 사용자가 접근 가능한 상태였다.

대응:

```bash
chmod 400 /home/ec2-user/MLO_01_001.pem
```

## 3. 연결 장애 점검 순서

```bash
whoami
rclone listremotes
rclone config file
rclone lsd gdrive:
rclone lsd "gdrive:MLOps 수업자료 모음/MLO-01-001-backup"
```

| 점검 결과 | 판단 |
|---|---|
| `gdrive:`가 없음 | remote 설정 또는 이름 문제 |
| 최상위 Drive 조회도 실패 | OAuth 또는 네트워크 문제 |
| 최상위 조회 성공, 특정 경로 실패 | 폴더가 아직 생성되지 않음 |
| 연결 시간 초과 | private subnet outbound 문제 |
| `permission denied` | OAuth 계정 또는 파일 공유 권한 문제 |

## 4. 보안 체크리스트

- [ ] OAuth 토큰 외부 공유 금지
- [ ] 클라이언트 보안 비밀 Git 커밋 금지
- [ ] rclone 설정 파일 권한 `600`
- [ ] SSH 개인 키 권한 `400` 또는 `600`
- [ ] 업로드 실행 사용자가 `ec2-user`인지 확인
- [ ] OAuth 앱 게시 상태와 테스트 사용자 확인


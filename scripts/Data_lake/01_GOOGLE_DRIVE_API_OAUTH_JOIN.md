# Google Drive API 및 OAuth 발급·연결 인수인계서

## 1. 목적

LogLake EC2에서 개인 Google Drive의 다음 경로로 파일을 전송하기 위한 인증 및 연결 구성 절차를 기록한다.

```text
내 드라이브/MLOps 수업자료 모음/MLO-01-001-backup
```

## 2. 기술 구성

| 구성요소 | 역할 |
|---|---|
| Google Drive API | 파일 및 폴더 접근 기능 제공 |
| OAuth 2.0 | 개인 Google 계정의 접근 동의 처리 |
| 데스크톱 OAuth 클라이언트 | rclone 사용자 인증에 사용 |
| rclone | EC2와 Google Drive 사이 파일 전송 |
| LogLake EC2 | 로그 저장 및 업로드 실행 서버 |

단순 API Key는 개인 Drive 파일에 대한 사용자 권한을 제공하지 않는다. 따라서 OAuth 2.0 클라이언트와 사용자 승인 토큰을 사용한다.

## 3. Google Cloud 설정 절차

1. Google Cloud Console에서 프로젝트를 생성한다.
2. API 및 서비스에서 Google Drive API를 활성화한다.
3. Google 인증 플랫폼에서 앱 이름과 사용자 지원 이메일을 입력한다.
4. 사용자 유형은 개인 계정 사용을 위해 `외부`로 설정한다.
5. 앱이 테스트 상태라면 사용할 Google 계정을 테스트 사용자로 등록한다.
6. OAuth 클라이언트를 생성하고 애플리케이션 유형은 `데스크톱 앱`으로 지정한다.
7. 발급된 클라이언트 ID와 클라이언트 보안 비밀을 안전하게 보관한다.

## 4. EC2 rclone 설정 절차

```bash
rclone config
```

설정 기준:

- 새 remote 생성: `n`
- remote 이름: `gdrive`
- Storage: Google Drive
- 사용자 Drive: 개인 `내 드라이브`
- Shared Drive: `No`

EC2는 브라우저가 없으므로 인증 명령이 표시되면 개인 PC에서 실행한다.

```bash
rclone authorize "drive" "클라이언트_정보"
```

개인 PC 작업 순서:

1. rclone 압축 파일을 내려받아 압축 해제한다.
2. PowerShell 또는 CMD에서 rclone을 실행한다.
3. 브라우저에서 사용할 Google 계정으로 로그인한다.
4. Google Drive 접근 권한을 승인한다.
5. 출력된 인증 결과를 EC2의 `config_token>`에 붙여 넣는다.
6. EC2에서 설정을 저장한다.

## 5. 설정 위치

| 항목 | 값 |
|---|---|
| 실행 사용자 | `ec2-user` |
| remote 이름 | `gdrive` |
| rclone 설정 | `/home/ec2-user/.config/rclone/rclone.conf` |
| Drive 루트 | `MLOps 수업자료 모음/MLO-01-001-backup` |

## 6. 연결 검증

```bash
rclone listremotes
```

정상 결과:

```text
gdrive:
```

Drive 접근 확인:

```bash
rclone lsd gdrive:
```

대상 폴더 생성 및 확인:

```bash
rclone mkdir "gdrive:MLOps 수업자료 모음/MLO-01-001-backup"
rclone lsd "gdrive:MLOps 수업자료 모음/MLO-01-001-backup"
```

테스트 파일 업로드:

```bash
date > /tmp/loglake-drive-test.txt
rclone copyto /tmp/loglake-drive-test.txt \
  "gdrive:MLOps 수업자료 모음/MLO-01-001-backup/loglake-drive-test.txt"
```

## 7. 네트워크 전제조건

LogLake가 private subnet에 있는 경우 Google API로 나갈 수 있는 HTTPS 경로가 필요하다.

- TCP 443 outbound 허용
- NAT Gateway, NAT 인스턴스 또는 승인된 외부 통신 경로

## 8. 보안 주의사항

```bash
chmod 600 /home/ec2-user/.config/rclone/rclone.conf
```

- `rclone.conf`에는 OAuth 토큰이 있으므로 GitHub에 커밋하지 않는다.
- OAuth 토큰과 클라이언트 보안 비밀을 화면 캡처로 공유하지 않는다.
- rclone 설정을 만든 `ec2-user`로 실행하고 불필요한 `sudo` 사용을 피한다.
- OAuth 앱이 테스트 상태이면 토큰 만료 가능성을 확인한다.

## 9. 완료 체크리스트

- [ ] Google Drive API 활성화
- [ ] OAuth 동의 화면 구성
- [ ] 사용할 계정을 테스트 사용자로 등록
- [ ] 데스크톱 OAuth 클라이언트 생성
- [ ] 개인 PC에서 사용자 승인 완료
- [ ] EC2에 `gdrive` remote 저장
- [ ] `rclone lsd gdrive:` 성공
- [ ] 지정 폴더 테스트 업로드 성공
- [ ] 토큰과 보안 비밀의 외부 노출 여부 확인


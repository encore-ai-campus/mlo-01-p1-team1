# PRD · 자동차 등록·FAQ 데이터 파이프라인

- document_id: `PRD-VF-001`
- version: `v5`
- document_state: `Draft`
- brd_reference: `BRD-VF-001@v1`
- scope_basis: `사용자가 확정한 최초 AWS·Python·cron·logrotate 기획만 반영`
- owner_role: `STK-PIPE-OPS-001`
- reviewer_roles: [`STK-CAR-DATA-001`, `STK-FAQ-DATA-001`, `STK-DQ-REV-001`]

## 1. 제품 정의와 범위

본 제품은 하나의 AWS 환경과 하나의 EC2에서 CAR·FAQ 원천 데이터를 Python으로 수집·파싱·정제·검증하여 각각 MySQL과 MongoDB에 적재하는 데이터 파이프라인이다. 단일 EC2 안에서 CAR worker·FAQ worker·MySQL·MongoDB를 별도 volume으로 분리한다.
EC2는 private subnet에 배치하고 SSM, `.pem`으로 관리하며, cron으로 pipeline을 자동 실행하고 단계별 오류 및 시스템 지표를 파일 로그로 기록한 뒤 `logrotate`로 회전·압축·보존한다.

### 1.1 포함 범위

- AWS VPC·subnet·IGW·단일 NAT Gateway·route table·security group 구성
- CAR worker·FAQ worker·MySQL·MongoDB를 포함하는 단일 EC2 구성
- Python `requests`·BeautifulSoup4·pandas 기반 수집·파싱·정제·품질검사
- CAR 데이터의 MySQL upsert와 FAQ 데이터의 MongoDB upsert
- cron 기반 자동 실행
- 수집·정제·DB 적재·시스템 지표 로그와 `logrotate`
- fixture 및 승인 원천을 이용한 정상·실패·중복 적재 검증

### 1.2 제외 범위

- Bastion, Main 등 추가 EC2, Google Drive 백업, 이메일 알림
- 별도 dev 서버 또는 prod/dev 이중 환경
- 사용자 UI·API·대시보드·ML 모델
- production HA·DR·다중 NAT·자동 failover·24시간 관제
- 승인되지 않은 원천 수집과 로그인·CAPTCHA·접근 제한 우회

## 2. 역할과 담당자

실제 담당자 이름은 작업 시작 전에 `<이름 입력>`을 교체한다.

| 역할 ID | 역할 | 담당 범위 | 실제 담당자 | 검토자 |
|---|---|---|---|---|
| `STK-PIPE-OPS-001` | AWS·자동화 담당자 | VPC·subnet·IGW·NAT·route·SG·단일 EC2·Docker Compose·SSM·cron·로그·logrotate | `<이름 입력>` | `STK-DQ-REV-001` |
| `STK-CAR-DATA-001` | CAR 데이터 담당자 | CAR 수집·파싱·정제·품질검사·MySQL 적재 | `<이름 입력>` | `STK-DQ-REV-001` |
| `STK-FAQ-DATA-001` | FAQ 데이터 담당자 | FAQ 수집·파싱·정제·품질검사·MongoDB 적재 | `<이름 입력>` | `STK-DQ-REV-001` |
| `STK-DQ-REV-001` | 품질·통합 검토자 | 데이터 계약·처리 건수·중복·실패 로그·evidence·보안 검토 | `<이름 입력>` | 나머지 팀원 1명 이상 |

## 3. AWS 아키텍처 요구사항

### 3.1 VPC와 subnet

| 리소스 | CIDR | 용도 |
|---|---|---|
| VPC | `10.0.0.0/16` | 프로젝트 단일 VPC |
| Public subnet1 | `10.0.1.0/24` | NAT Gateway |
| Public subnet2 | `10.0.3.0/24` | 예비 subnet |
| Private subnet1 | `10.0.5.0/24` | Car Data Crawling Server, mysqldb server |
| Private subnet2 | `10.0.7.0/24` | FAQ Data Crawling Server, mongodb server |

### 3.2 Internet Gateway·NAT·route table

| 리소스 | 연결·경로 | 합격 기준 |
|---|---|---|
| Internet Gateway | VPC에 연결 | NAT Gateway의 인터넷 경로 제공 |
| NAT Gateway | Public subnet1에 생성하고 Elastic IP 연결 | Private subnet1, 2의 Outbound 트래픽을 공인 IP를 붙여서 외부로 내보내는지 확인  |
| `rt-public` | `0.0.0.0/0 → IGW`, Public subnet1·2 연결 | NAT의 인터넷 경로 확인 |
| `rt-private` | `0.0.0.0/0 → NAT`, Private subnet1·2 연결 | private EC2 outbound 가능, 외부 inbound 불가 |

단일 NAT Gateway와 단일 EC2 사용은 본 프로젝트의 범위 제약이다. NAT·EC2 장애 이중화는 Out of scope다.

### 3.3 단일 EC2 서비스 분리

| 구성 요소 | 배치 | 역할 | owner |
|---|---|---|---|
| Pipeline EC2 | Private subnet1, Private IP only | Docker·cron·로그·logrotate·시스템 지표 | `STK-PIPE-OPS-001` |
| `car-worker` | internal network | CAR 수집·정제·품질검사 | `STK-CAR-DATA-001` |
| `faq-worker` | internal network | FAQ 수집·정제·품질검사 | `STK-FAQ-DATA-001` |
| `mysql` | internal network | CAR 정본 저장소 | `STK-CAR-DATA-001` |
| `mongodb` | internal network | FAQ 정본 저장소 | `STK-FAQ-DATA-001` |

권장 디렉터리를 분리하여 저정한다.

```text
/opt/pipeline/car/
/opt/pipeline/faq/
/data/mysql/
/data/mongodb/
/var/log/car-pipeline/
/var/log/faq-pipeline/
```

### 3.4 접근·보안 경계

- EC2에는 Public IP를 부여하지 않고 SSM Session Manager or `.pem`로 접속한다.
- EC2 security group은 mongodb, mysql포트 접속과 ssh inbound연결과 필요한 outbound만 허용한다.
- MySQL `3306`과 MongoDB `27017`은 host public interface에 노출하지 않는다.
- `car-worker`는 MySQL에만, `faq-worker`는 MongoDB에만 접근하도록 DB 사용자 권한을 분리한다.
- 단일 EC2 장애 시 CAR·FAQ·MySQL·MongoDB가 동시에 중단되는 위험을 수용한다.


## 4. 기능·데이터·운영 요구사항 catalog

상태 값은 `planned | in_progress | pass | fail | not_verified` 중 하나를 사용한다.

| ID | 상태 | 요구사항 | BRD 목표 | AC | owner | due |
|---|---|---|---|---|---|---|
| `FR-AWS-VPC-001` | planned | 지정 CIDR로 VPC와 public·private subnet 각 2개를 생성한다. | `BR-OBJ-003` | `AC-AWS-NET-001` | `STK-PIPE-OPS-001` | Day 1 |
| `FR-AWS-EGRESS-001` | planned | IGW와 Public subnet1의 단일 NAT Gateway를 구성한다. | `BR-OBJ-003` | `AC-AWS-NET-001` | `STK-PIPE-OPS-001` | Day 1 |
| `FR-AWS-ROUTE-001` | planned | public route와 private1, 2 route를 요구된 public subnet에 연결한다. | `BR-OBJ-003` | `AC-AWS-ROUTE-001` | `STK-PIPE-OPS-001` | Day 1 |
| `FR-AWS-EC2-001` | planned | Private subnet1, 2에 pipeline EC2를 생성한다. | `BR-OBJ-003` | `AC-AWS-EC2-001` | `STK-PIPE-OPS-001` | Day 1 |
| `FR-COMPOSE-001` | planned | private subnet1, 2의 EC2에서 car-worker·faq-worker·mysql·mongodb 서비스를 분리한다. | `BR-OBJ-003` | `AC-COMPOSE-001` | `STK-PIPE-OPS-001` | Day 1 |
| `NFR-AWS-ACCESS-001` | planned | EC2에 Public IP를 두지않고, mongodb, mysql port 및 ssh 연결을 제외한 inbound를 두지 않고 관리한다. | `BR-OBJ-004` | `AC-AWS-SG-001` | `STK-PIPE-OPS-001` | Day 1 |
| `FR-CAR-COLLECT-001` | planned | 승인된 CAR URL에 timeout을 적용해 요청하고 응답 성공 여부를 기록한다. | `BR-OBJ-001` | `AC-CAR-COLLECT-001` | `STK-CAR-DATA-001` | Day 1 |
| `FR-CAR-PARSE-001` | planned | BeautifulSoup4로 CAR 대상 영역을 파싱하고 `필요한 필드를 추출`한다. | `BR-OBJ-001` | `AC-CAR-TRANSFORM-001` | `STK-CAR-DATA-001` | Day 1 |
| `FR-CAR-FRAME-001` | planned | CAR 추출 결과를 정의된 컬럼과 타입의 DataFrame으로 변환한다. | `BR-OBJ-001` | `AC-CAR-TRANSFORM-001` | `STK-CAR-DATA-001` | Day 1 |
| `FR-CAR-CLEAN-001` | planned | 기준월·지역·차종·등록대수를 표준화하고 원본 값과 정제 값을 추적한다. | `BR-OBJ-001` | `AC-CAR-QUALITY-001` | `STK-CAR-DATA-001` | Day 1 |
| `DR-CAR-001` | planned | CAR 결측·중복·형식·비음수·처리 건수 대사를 검사한다. | `BR-OBJ-001`·`BR-OBJ-004` | `AC-CAR-QUALITY-001` | `STK-CAR-DATA-001` | Day 1 |
| `FR-CAR-LOAD-001` | planned | 품질검사를 통과한 CAR 데이터를 business key 기준으로 MySQL에 upsert한다. | `BR-OBJ-001` | `AC-CAR-LOAD-001` | `STK-CAR-DATA-001` | Day 1 |
| `FR-FAQ-COLLECT-001` | planned | 승인된 FAQ URL에 timeout을 적용해 요청하고 응답 성공 여부를 기록한다. | `BR-OBJ-002` | `AC-FAQ-COLLECT-001` | `STK-FAQ-DATA-001` | Day 1 |
| `FR-FAQ-PARSE-001` | planned | BeautifulSoup4로 FAQ 대상 영역을 파싱하고 필요한 필드를 추출한다. | `BR-OBJ-002` | `AC-FAQ-TRANSFORM-001` | `STK-FAQ-DATA-001` | Day 1 |
| `FR-FAQ-FRAME-001` | planned | FAQ 추출 결과를 정의된 컬럼과 타입의 DataFrame으로 변환한다. | `BR-OBJ-002` | `AC-FAQ-TRANSFORM-001` | `STK-FAQ-DATA-001` | Day 1 |
| `FR-FAQ-CLEAN-001` | planned | 회사·카테고리·질문·답변·URL을 표준화하고 원본 값과 정제 값을 추적한다. | `BR-OBJ-002` | `AC-FAQ-QUALITY-001` | `STK-FAQ-DATA-001` | Day 1 |
| `DR-FAQ-001` | planned | FAQ 결측·중복·빈 내용·URL 형식·처리 건수 대사를 검사한다. | `BR-OBJ-002`·`BR-OBJ-004` | `AC-FAQ-QUALITY-001` | `STK-FAQ-DATA-001` | Day 1 |
| `FR-FAQ-LOAD-001` | planned | 품질검사를 통과한 FAQ를 고유 식별키 기준으로 MongoDB에 upsert한다. | `BR-OBJ-002` | `AC-FAQ-LOAD-001` | `STK-FAQ-DATA-001` | Day 1 |
| `FR-CRON-CAR-001` | planned | CAR pipeline cron entry를 private subnet1 EC2에 등록한다. | `BR-OBJ-003` | `AC-CRON-001` | `STK-PIPE-OPS-001` | Day 2 |
| `FR-CRON-FAQ-001` | planned | FAQ pipeline cron entry를 private subnet2 EC2에 등록한다. | `BR-OBJ-003` | `AC-CRON-001` | `STK-PIPE-OPS-001` | Day 2 |
| `FR-LOG-001` | planned | 수집·정제·적재 단계별 시작·성공·실패·처리 건수 로그를 파일로 기록한다. | `BR-OBJ-003`·`BR-OBJ-004` | `AC-LOG-001` | `STK-PIPE-OPS-001` | Day 2 |
| `FR-SYSTEM-METRIC-001` | planned | CPU·memory·disk 사용량을 주기적으로 파일 로그에 기록한다. | `BR-OBJ-003` | `AC-SYSTEM-METRIC-001` | `STK-PIPE-OPS-001` | Day 2 |
| `FR-LOGROTATE-001` | planned | crawler·transform·loader·system metric 로그에 logrotate 정책을 적용한다. | `BR-OBJ-003` | `AC-LOGROTATE-001` | `STK-PIPE-OPS-001` | Day 2 |
| `NFR-IDEMP-001` | planned | 동일 입력을 재실행해도 MySQL row와 MongoDB document가 중복 증가하지 않는다. | `BR-OBJ-003` | `AC-IDEMP-001` | `STK-DQ-REV-001` | Day 2 |
| `NFR-SECRET-001` | planned | DB 비밀번호·API key·private endpoint를 코드·Git·로그에 기록하지 않는다. | `BR-OBJ-004` | `AC-SECRET-001` | `STK-DQ-REV-001` | Day 2 |

## 5. 데이터 계약

실제 원천 확인 후 필드명은 변경할 수 있으나 business key와 필수 여부는 적재 전에 확정해야 한다.

### 5.1 CAR MySQL table

권장 table명: `car_registration`

| 필드 | 타입 예시 | 필수 | 검증 규칙 |
|---|---|---|---|
| `base_month` | `CHAR(6)` | Y | `YYYYMM` 형식 |
| `region_code` | `VARCHAR(20)` | Y | 공백·null 금지 |
| `region_name` | `VARCHAR(100)` | Y | 표준 지역명 |
| `vehicle_type_code` | `VARCHAR(20)` | Y | 공백·null 금지 |
| `vehicle_type_name` | `VARCHAR(100)` | Y | 표준 차종명 |
| `registration_count` | `INT` | Y | 0 이상 |
| `source_url` | `TEXT` | Y | 승인 URL |
| `collected_at` | `DATETIME` | Y | 수집 시각 |
| `raw_hash` | `CHAR(64)` | Y | 원본 추적 checksum |

- CAR business key: `base_month + region_code + vehicle_type_code`
- 동일 business key는 `INSERT`가 아니라 `UPDATE` 또는 변경 없음으로 처리한다.

### 5.2 FAQ MongoDB collection

권장 collection명: `faqs`

| 필드 | 타입 예시 | 필수 | 검증 규칙 |
|---|---|---|---|
| `company_id` | string | Y | 승인된 회사 ID |
| `source_key` | string | Y | 원천에서 FAQ를 식별하는 값 |
| `category` | string | Y | 공백 정리 |
| `question` | string | Y | 빈 문자열 금지 |
| `answer` | string | Y | 빈 문자열 금지 |
| `source_url` | string | Y | 승인 URL |
| `content_hash` | string | Y | 질문·답변 변경 식별 |
| `collected_at` | datetime | Y | 수집 시각 |

- FAQ 고유 식별키: `company_id + source_key`
- 동일 식별키의 내용이 같으면 중복 추가하지 않고, `content_hash`가 다르면 갱신한다.

## 6. Python 처리 흐름

### 6.1 공통 처리 단계

```text
collect → parse → extract → dataframe → clean → quality → load → log
```

| 단계 | 구현 내용 | 통과 기준 |
|---|---|---|
| collect | `requests.get(url, timeout=<설정값>)` 실행 | `response.ok is True`, 응답 시각·URL·status 기록 |
| parse | BeautifulSoup4로 대상 영역 선택 | 대상 selector가 존재하고 파싱 결과가 비어 있지 않음 |
| extract | 필요한 필드만 추출 | 필수 필드 누락 행이 식별됨 |
| dataframe | pandas DataFrame 변환 | 컬럼명·타입·필수 여부가 데이터 계약과 일치 |
| clean | 날짜·지역·차종·문자열·URL 표준화 | 원본 값과 정제 값을 비교 가능 |
| quality | 결측·중복·형식·허용 범위·건수 대사 | 기준 초과 시 load 중단 |
| load | CAR→MySQL, FAQ→MongoDB upsert | 대상 DB·table·collection·key가 정확함 |
| log | 단계별 상태와 count 기록 | 실패 단계와 정제 오류를 확인 가능 |

### 6.2 실패 경계

- 요청 실패 또는 존재하지 않는 URL은 `crawler.log`에 남기고 parse·load를 수행하지 않는다.
- selector가 없거나 필수 필드가 누락되면 `transform.log`에 남기고 해당 데이터를 정상 건수에 포함하지 않는다.
- 품질 허용 기준을 초과하면 DB 적재를 중단한다.
- MySQL·MongoDB 연결 또는 적재 실패는 `loader.log`에 남기고 완료 상태로 표시하지 않는다.
- 로그에는 credential·전체 connection string·민감정보를 남기지 않는다.

## 7. cron·로그·logrotate 요구사항

### 7.1 cron

단일 EC2에는 CAR·FAQ pipeline cron entry를 각각 하나만 등록한다.

```text
# project-car-pipeline
<schedule> /usr/bin/python3 <car-entrypoint> >> /var/log/car-pipeline/cron.log 2>&1

# project-faq-pipeline
<schedule> /usr/bin/python3 <faq-entrypoint> >> /var/log/faq-pipeline/cron.log 2>&1
```

검증 명령 예시:

```bash
crontab -l | grep -c '# project-car-pipeline'
crontab -l | grep -c '# project-faq-pipeline'
```

두 명령의 결과가 각각 `1`이면 PASS다. 단순히 `grep python3`를 사용하면 다른 Python cron까지 집계할 수 있으므로 프로젝트 식별 주석을 기준으로 검사한다.

### 7.2 로그 파일

```text
/var/log/car-pipeline/crawler.log
/var/log/car-pipeline/transform.log
/var/log/car-pipeline/loader.log
/var/log/car-pipeline/system-metrics.log

/var/log/faq-pipeline/crawler.log
/var/log/faq-pipeline/transform.log
/var/log/faq-pipeline/loader.log
/var/log/faq-pipeline/system-metrics.log
```

로그의 최소 필드는 다음과 같다.

```text
timestamp, pipeline, stage, status, source_url, raw_count,
valid_count, error_count, loaded_count, duration_ms, error_code, error_message
```

### 7.3 logrotate 정책

단일 EC2에 `/etc/logrotate.d/car-pipeline`, `/etc/logrotate.d/faq-pipeline`을 각각 둔다.

```text
daily
rotate 7
compress
delaycompress
missingok
notifempty
dateext
dateformat -%Y%m%d
create 0640
```

시스템 지표는 CPU·memory·disk 사용률을 별도 스크립트로 기록하고 동일한 logrotate 정책을 적용한다.

검증 명령 예시:

```bash
sudo logrotate -d /etc/logrotate.d/car-pipeline
sudo logrotate -f /etc/logrotate.d/car-pipeline
sudo logrotate -d /etc/logrotate.d/faq-pipeline
sudo logrotate -f /etc/logrotate.d/faq-pipeline
```

`-d`는 설정 오류 확인용이며 실제 회전은 수행하지 않는다. 강제 회전 후 기존 로그가 분리·압축되고 새 로그에 후속 기록이 가능하면 PASS다.

## 8. Acceptance criteria

| AC ID | Given | When | Then | Evidence | 상태 |
|---|---|---|---|---|---|
| `AC-AWS-NET-001` | 빈 AWS 프로젝트 환경 | VPC·subnet·IGW·NAT 생성 | CIDR이 설계와 일치하고 NAT가 Public subnet1에서 Available | `evidence/aws-network.md` | planned |
| `AC-AWS-ROUTE-001` | 생성된 IGW·NAT·subnet | route table 연결 | public은 IGW, private1·2는 NAT로 outbound 연결 | `evidence/aws-network.md` | planned |
| `AC-AWS-EC2-001` | network 생성 완료 | 단일 EC2 생성 | EC2가 Private subnet1에 Public IP 없이 배치되고 SSM 접속 가능 | `evidence/aws-ec2.md` | planned |
| `AC-COMPOSE-001` | Docker가 설치된 단일 EC2 | `docker compose up` 실행 | car-worker·faq-worker·mysql·mongodb가 분리된 서비스와 volume으로 실행 | `evidence/docker-compose.md` | planned |
| `AC-AWS-SG-001` | EC2와 SG 생성 완료 | 접근·포트 검사 | Public inbound가 없고 3306·27017이 외부에 노출되지 않음 | `evidence/aws-security-group.md` | planned |
| `AC-CAR-COLLECT-001` | 정상 URL과 존재하지 않는 URL | CAR collector 실행 | 정상 응답은 raw로 처리되고 실패 URL은 crawler log에 기록되며 load되지 않음 | `evidence/car-pipeline.md` | planned |
| `AC-CAR-TRANSFORM-001` | 정상·필수값 누락 CAR fixture | parse·DataFrame 변환 | 정상 필드가 계약과 일치하고 누락 행이 별도 식별 | `evidence/car-pipeline.md` | planned |
| `AC-CAR-QUALITY-001` | 결측·중복·음수·형식 오류 CAR fixture | clean·quality 실행 | 오류가 분류되고 원본 건수 = 정상 후보 + 오류 건수 | `output/<run_id>/car-quality-report.json` | planned |
| `AC-CAR-LOAD-001` | 유효 CAR 데이터 | MySQL load 실행 | business key 중복 0건, 유효 후보와 DB 대상 건수 차이 0건 | `evidence/mysql-verification.md` | planned |
| `AC-FAQ-COLLECT-001` | 정상 URL과 존재하지 않는 URL | FAQ collector 실행 | 정상 응답은 raw로 처리되고 실패 URL은 crawler log에 기록되며 load되지 않음 | `evidence/faq-pipeline.md` | planned |
| `AC-FAQ-TRANSFORM-001` | 정상·필수값 누락 FAQ fixture | parse·DataFrame 변환 | 정상 필드가 계약과 일치하고 누락 document가 별도 식별 | `evidence/faq-pipeline.md` | planned |
| `AC-FAQ-QUALITY-001` | 결측·중복·빈 질문·빈 답변 fixture | clean·quality 실행 | 오류가 분류되고 원본 건수 = 정상 후보 + 오류 건수 | `output/<run_id>/faq-quality-report.json` | planned |
| `AC-FAQ-LOAD-001` | 유효 FAQ 데이터 | MongoDB load 실행 | 고유 식별키 중복 0건, 유효 후보와 collection 대상 건수 차이 0건 | `evidence/mongodb-verification.md` | planned |
| `AC-CRON-001` | 수동 실행 성공 | 단일 EC2에 cron 등록 후 목록 검사 | CAR·FAQ pipeline cron entry가 각각 정확히 1개 | `evidence/cron-logrotate.md` | planned |
| `AC-LOG-001` | 성공·실패 fixture | 각 pipeline 실행 | 수집·정제·적재 로그에서 단계·상태·건수·정제 오류 확인 | `evidence/cron-logrotate.md` | planned |
| `AC-SYSTEM-METRIC-001` | metric script와 cron | CPU·memory·disk 로그 생성 | 세 지표와 측정 시각이 system-metrics.log에 기록 | `evidence/system-metrics.md` | planned |
| `AC-LOGROTATE-001` | 회전 대상 로그 | logrotate dry run과 강제 회전 | 설정 오류가 없고 회전 파일 생성 후 새 로그 기록 가능 | `evidence/cron-logrotate.md` | planned |
| `AC-IDEMP-001` | 동일한 CAR·FAQ 입력 | 각 pipeline을 2회 실행 | 두 번째 실행 후 MySQL·MongoDB business record 수가 중복 증가하지 않음 | `evidence/idempotency.md` | planned |
| `AC-SECRET-001` | 코드·설정·로그 제출 후보 | 민감정보 검사 | credential·private endpoint·개인정보 의심 항목 0건 | `evidence/security-review.md` | planned |

## 9. 담당자별 구현 체크리스트

### 9.1 AWS·자동화 담당자

- [ ] VPC `10.0.0.0/16` 생성
- [ ] Public subnet1·2와 Private subnet1·2 생성
- [ ] IGW 연결과 `rt-public` 구성
- [ ] Public subnet1에 NAT Gateway 생성
- [ ] Private subnet1·2의 default route를 NAT로 연결
- [ ] Private subnet1에 단일 pipeline EC2 생성
- [ ] EC2 Public IP 없음과 SSM 접속 확인
- [ ] Docker·Docker Compose 설치
- [ ] car-worker·faq-worker·mysql·mongodb 서비스와 전용 volume 구성
- [ ] SG에 Public inbound가 없고 3306·27017이 host 외부에 노출되지 않음을 확인
- [ ] CAR·FAQ cron entry 각 1개 등록
- [ ] crawler·transform·loader·system metric 로그 경로 생성
- [ ] CAR·FAQ logrotate dry run·강제 회전 검증
- [ ] AWS·cron·logrotate evidence 작성

### 9.2 CAR 데이터 담당자

- [ ] CAR 승인 URL과 fixture 확정
- [ ] `requests` collector와 실패 로그 구현
- [ ] BeautifulSoup selector와 필수 필드 추출 구현
- [ ] DataFrame schema와 정제 규칙 구현
- [ ] 결측·중복·형식·음수·건수 대사 구현
- [ ] MySQL table·unique key·upsert 구현
- [ ] 정상·실패·동일 입력 2회 테스트
- [ ] CAR quality report와 MySQL evidence 작성

### 9.3 FAQ 데이터 담당자

- [ ] FAQ 승인 URL과 fixture 확정
- [ ] `requests` collector와 실패 로그 구현
- [ ] BeautifulSoup selector와 필수 필드 추출 구현
- [ ] DataFrame schema와 정제 규칙 구현
- [ ] 결측·중복·빈 질문·빈 답변·건수 대사 구현
- [ ] MongoDB collection·unique index·upsert 구현
- [ ] 정상·실패·동일 입력 2회 테스트
- [ ] FAQ quality report와 MongoDB evidence 작성

### 9.4 품질·통합 검토자

- [ ] BRD 목표와 PRD 요구사항·AC 연결 확인
- [ ] CAR·FAQ business key와 필수 필드 확인
- [ ] 원본·정상·오류·적재 건수 대사 확인
- [ ] invalid URL이 DB에 적재되지 않았는지 확인
- [ ] MySQL·MongoDB 중복 증가가 0건인지 확인
- [ ] 단일 EC2에서 CAR·FAQ cron entry가 각각 정확히 1개인지 확인
- [ ] logrotate 후 로그 유실 없이 후속 기록되는지 확인
- [ ] credential·private endpoint·개인정보 노출 0건 확인
- [ ] evidence가 없는 항목을 PASS로 표시하지 않았는지 확인

## 10. 2일 구현 순서

| 일차 | 작업 | owner | 완료 evidence |
|---|---|---|---|
| Day 1 오전 | VPC·subnet·IGW·NAT·route·SG·단일 EC2·Docker Compose 구성 | AWS·자동화 담당자 | `evidence/aws-network.md`, `evidence/aws-ec2.md`, `evidence/docker-compose.md` |
| Day 1 오전 | CAR·FAQ source·schema·fixture·business key 확정 | CAR·FAQ·품질 담당자 | data contract review note |
| Day 1 오후 | CAR pipeline과 MySQL upsert | CAR 담당자 | `evidence/car-pipeline.md`, `evidence/mysql-verification.md` |
| Day 1 오후 | FAQ pipeline과 MongoDB upsert | FAQ 담당자 | `evidence/faq-pipeline.md`, `evidence/mongodb-verification.md` |
| Day 2 오전 | cron·단계별 로그·system metric·logrotate | AWS·자동화 담당자 | `evidence/cron-logrotate.md` |
| Day 2 오후 | 실패·멱등성·보안·전체 통합 검증 | 품질 검토자와 전원 | `evidence/idempotency.md`, `evidence/security-review.md` |

## 11. 검토와 baseline

| reviewed_at | reviewer_role | review_result | note |
|---|---|---|---|
| `<TODO: YYYY-MM-DD>` | `STK-CAR-DATA-001` | `PASS \| FAIL \| NOT_VERIFIED` | `<TODO>` |
| `<TODO: YYYY-MM-DD>` | `STK-FAQ-DATA-001` | `PASS \| FAIL \| NOT_VERIFIED` | `<TODO>` |
| `<TODO: YYYY-MM-DD>` | `STK-PIPE-OPS-001` | `PASS \| FAIL \| NOT_VERIFIED` | `<TODO>` |
| `<TODO: YYYY-MM-DD>` | `STK-DQ-REV-001` | `PASS \| FAIL \| NOT_VERIFIED` | `<TODO>` |

- 실제 담당자 이름·source·business key·cron 주기가 확정될 때까지 `Draft`를 유지한다.
- AWS·DB·pipeline·cron·logrotate를 실제로 검증하기 전에는 `PASS` 대신 `planned` 또는 `NOT_VERIFIED`를 사용한다.
- 모든 Must 요구사항에 AC와 evidence가 연결되고 orphan 요구사항이 0건일 때만 `Baselined`로 변경한다.
- 실제 credential·private endpoint·개인정보는 PRD와 evidence에 기록하지 않는다.
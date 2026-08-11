# BRD·PRD 작업 진행 가이드

- 작성일: `2026-08-11`
- 대상 프로젝트: 자동차 등록·FAQ 데이터 파이프라인
- 목적: 현재까지 확정한 내용을 정리하고 BRD·PRD에 추가로 작성할 항목, 작성 시 유의사항, 2일 MVP의 핵심 완료 기준을 공유한다.

## 1. 프로젝트 핵심

이 프로젝트의 핵심은 단순히 데이터를 자동 수집하는 것이 아니라, **승인된 원천의 데이터를 정해진 품질 기준으로 처리하고 실패를 성공으로 표시하지 않으며, 실행·오류·재실행·백업 결과를 추적 가능하게 만드는 것**이다.

핵심 구성은 다음과 같다.

- CAR 데이터: 수집·정제·품질검사 후 MySQL에 upsert
- FAQ 데이터: 수집·정제·품질검사 후 MongoDB에 upsert
- 단일 EC2: CAR worker·FAQ worker·MySQL·MongoDB·cron·로그를 Docker Compose와 별도 volume으로 분리
- 로그: EC2에서 구조화 JSONL로 기록하고 `logrotate`로 회전·압축·보존
- 검증: 동일 입력 재실행 시 중복이 생기지 않고, 실패 단계와 근거를 evidence로 확인

이 구조는 사용자 화면–애플리케이션–DB로 구성된 전통적인 3-Tier가 아니라, **단일 EC2 안에서 CAR·FAQ·MySQL·MongoDB 서비스를 논리 분리한 데이터 파이프라인 구조**다.

## 2. 현재 문서 진행 상태

| 문서 | 현재 상태 | 확인 결과 | 다음 조치 |
|---|---|---|---|
| [BRD](./brd.md) | `v1 Draft` | 이전 이해관계자 ID와 starter용 TODO가 남아 있음 | 확정한 네 역할·목표·범위·제약으로 갱신 |
| [PRD](./prd.md) | `v5 Draft` | 단일 EC2·Docker Compose·MySQL·MongoDB·cron·logrotate 요구가 반영됨 | 실제 담당자·source·business key·cron 주기 확정 |
| [요구사항 추적표](./requirements-traceability.md) | `v1 Draft` | 이전 PRD의 15개 요구사항과 예전 ID를 참조함 | PRD v3의 18개 Must 요구사항 기준으로 재작성 |
| [Project Plan](../project-plan.md) | `v1 Draft` | Day 21~23의 3일 일정과 이전 요구사항 ID를 사용함 | 실제 2일 일정과 네 역할 기준으로 변경 |
| [Change Log](./change-log.md) | baseline 전 | baseline 이후 변경 기록용 | 현재는 Draft이므로 의미 변경보다 review note 중심으로 관리 |

### 가장 먼저 해결할 문서 불일치

1. PRD는 `BR-OBJ-CAR-001`, `BR-OBJ-FAQ-001`, `BR-OBJ-OPS-001`, `BR-OBJ-DQ-001`을 참조하지만 현재 BRD에는 이 ID가 없다.
2. BRD의 이해관계자 ID가 확정한 `STK-FAQ-DATA-001`, `STK-CAR-DATA-001`, `STK-PIPE-OPS-001`, `STK-DQ-REV-001`과 다르다.
3. 추적표는 이전 `FR-VEH-*`, `FR-RUN-001`, `NFR-OBS-001` 등을 참조하여 PRD v3와 연결되지 않는다.
4. Project Plan은 3일 일정이지만 실제 목표 일정은 2일이다.
5. 추적표와 Project Plan에는 단일 EC2·Docker Compose·cron·logrotate 요구사항이 아직 반영되지 않았다.

이 다섯 항목을 해결하기 전에는 BRD·PRD를 `Baselined`로 변경하지 않는다.

## 3. BRD에 작성해야 할 내용

BRD는 구현 방법보다 **왜 필요한지, 누구에게 어떤 결과가 필요한지, 어디까지 수행하는지**를 기록한다.

### 3.1 이해관계자

| ID | 역할 | 필요한 업무 결과 |
|---|---|---|
| `STK-FAQ-DATA-001` | FAQ 데이터 담당자 | 승인된 FAQ 데이터를 정제·검증하여 MongoDB에 저장하고 출처와 품질 결과를 확인한다. |
| `STK-CAR-DATA-001` | CAR 데이터 담당자 | 승인된 자동차 데이터를 기준월·지역·차종 기준으로 정제·검증하여 MySQL에 저장한다. |
| `STK-PIPE-OPS-001` | 파이프라인 운영자 | 실행 상태와 실패 단계를 확인하고 중복이나 데이터 훼손 없이 재실행한다. |
| `STK-DQ-REV-001` | 데이터 품질 검토자 | 원천·스키마·처리 건수·로그·백업 evidence로 결과의 신뢰성을 판정한다. |

### 3.2 업무 목표와 측정 방법

BRD 목표는 다음 네 가지로 맞춘다.

| 목표 ID | 목표 | 최소 통과 기준 |
|---|---|---|
| `BR-OBJ-FAQ-001` | FAQ 데이터의 품질과 출처를 보장 | 필수값·고유키·출처 누락 0건, 완전수집 상태 기록 |
| `BR-OBJ-CAR-001` | CAR 데이터의 품질과 출처를 보장 | 필수값·음수·중복 오류가 적재되지 않고 건수 대사 일치 |
| `BR-OBJ-OPS-001` | 실행·실패·재실행을 안전하게 관리 | 동일 입력 재실행 중복 0건, 실패 단계와 상태 확인 가능 |
| `BR-OBJ-DQ-001` | 요구사항과 실행 결과를 근거로 검토 | 모든 Must 요구가 AC·evidence에 연결되고 근거 누락 0건 |

### 3.3 In scope

- FAQ 담당: 승인된 FAQ 수집·정제·품질검사·MongoDB 적재·출처 이력 관리
- CAR 담당: 승인된 자동차 데이터 수집·표준화·품질검사·MySQL 적재·출처 이력 관리
- 파이프라인 운영: 단일 EC2·Docker Compose·cron·멱등성·구조화 로그·logrotate 관리
- 품질 검토: 원천·스키마·품질·처리 건수·로그·백업·요구사항 evidence 검토

### 3.4 Out of scope

- FAQ 담당: 승인되지 않은 수집, 접근 제한 우회, FAQ 생성·추천·분석
- CAR 담당: 차량·소유자 개인정보, 실시간 처리, 예측·분석 모델
- 파이프라인 운영: 사용자용 UI·API·대시보드, production HA·DR·24시간 관제
- 품질 검토: 원본·DB 직접 수정, 외부 기관의 법적·규제 감사

### 3.5 규칙·제약·가정

- CAR는 MySQL, FAQ는 MongoDB를 정본 저장소로 사용한다.
- 승인된 원천과 범위만 수집하고 source·schema가 불명확하면 DB에 쓰지 않는다.
- credential·private endpoint·개인정보는 문서·Git·로그·Drive에 기록하지 않는다.
- 동일 입력 재실행은 중복을 만들지 않으며 실패 실행은 마지막 성공 상태를 변경하지 않는다.
- live source 사용이 어려우면 동일 구조의 승인 fixture로 검증한다.

### 3.6 BRD 작성 유의사항

- 서버 포트·라이브러리·함수명·폴더 경로 같은 구현 세부사항은 BRD가 아니라 PRD·architecture에 기록한다.
- “수집한다”보다 “어떤 업무 결과를 얻는가”가 먼저 보여야 한다.
- 측정 방법은 “정상 작동”이 아니라 누락 건수·중복 건수·대사 결과처럼 PASS/FAIL이 가능해야 한다.
- 아직 확인하지 않은 실제 원천·EC2·DB 결과를 완료 또는 PASS로 쓰지 않는다.
- 일정·담당자의 상세 작업은 Project Plan에서 관리하고 BRD에 반복하지 않는다.

## 4. PRD에 작성해야 할 내용

PRD는 **시스템이 무엇을 해야 하고 어떤 조건에서 완료로 인정할지**를 기록한다.

### 4.1 CAR 요구사항

- 승인된 기준월 raw 수집
- 기준월·지역·차종·등록대수 구조로 정제
- 필수값·날짜·코드·음수·중복 검사
- business key 기준 MySQL upsert
- 원본·정상·오류·저장 건수 대사

### 4.2 FAQ 요구사항

- 승인된 기업과 allowlist URL만 수집
- 회사·카테고리·질문·답변·원문 주소 구조로 정제
- 식별키·content hash·출처·완전수집 상태 보존
- 고유 식별키 기준 MongoDB upsert
- 일부 페이지 실패 시 기존 FAQ 삭제·비활성화 금지

### 4.3 단일 EC2 요구사항

- EC2는 Private subnet에 배치하고 Public IP 없이 SSM으로 관리한다.
- CAR worker·FAQ worker·MySQL·MongoDB는 Docker Compose 서비스로 분리한다.
- MySQL·MongoDB는 서로 다른 persistent volume을 사용한다.
- MySQL 3306과 MongoDB 27017은 host 외부에 공개하지 않는다.
- CAR worker는 MySQL에만, FAQ worker는 MongoDB에만 접근하도록 권한을 분리한다.
- 단일 EC2 장애가 모든 서비스에 영향을 주는 위험을 수용한다.

### 4.4 로그·자동화 요구사항

- CAR·FAQ는 단계별 JSONL 로그를 별도 경로에 남긴다.
- 로그에는 `run_id`, environment, dataset, event, stage, status, count, duration, 발생 시각, 정제 오류를 포함한다.
- CAR·FAQ cron entry를 단일 EC2에 각각 하나만 등록한다.
- `logrotate`는 crawler·transform·loader·system metric 로그를 회전·압축·보존한다.
- CPU·memory·disk 사용량을 주기적으로 system-metrics.log에 기록한다.

### 4.5 PRD 작성 유의사항

- 한 요구사항에는 가능한 한 하나의 검증 가능한 동작만 작성한다.
- 모든 `Must do` 요구사항에는 최소 하나의 AC를 연결한다.
- AC는 `Given–When–Then–Evidence` 구조로 작성한다.
- `logrotate`를 장애 감지 도구로 표현하지 않는다.
- CAR 실패가 FAQ 성공 데이터를 rollback하거나, FAQ 실패가 CAR 성공 데이터를 rollback하지 않도록 실패 경계를 분리한다.
- CAR·FAQ·MySQL·MongoDB가 같은 EC2 자원을 사용한다는 제약과 자원 충돌 위험을 기록한다.
- 구현 전인 evidence는 `planned`, 확인하지 못한 외부 결과는 `NOT_VERIFIED`로 유지한다.

## 5. 현재 확정해야 할 미결 질문

| 우선순위 | 질문 | 결정 owner |
|---|---|---|
| 1 | CAR business key의 최종 필드는 무엇인가? | `STK-CAR-DATA-001` |
| 1 | FAQ 고유 식별키와 완전수집 기준은 무엇인가? | `STK-FAQ-DATA-001` |
| 1 | CAR·FAQ 실제 원천과 fixture 범위는 무엇인가? | 각 데이터 담당자 |
| 1 | 단일 EC2의 인스턴스 크기·volume 용량·SSM 접근 방식은 무엇인가? | `STK-PIPE-OPS-001` |
| 2 | 실행 주기와 동시 실행 잠금 방식은 무엇인가? | `STK-PIPE-OPS-001` |
| 2 | EC2 로그 회전 기준과 보존 기간은 얼마인가? | `STK-PIPE-OPS-001` |

## 6. 2일 MVP 범위

### 반드시 완료할 항목

- CAR fixture 1종을 MySQL까지 end-to-end 적재
- FAQ fixture 1종을 MongoDB까지 end-to-end 적재
- 단일 EC2의 Docker Compose에서 CAR·FAQ·MySQL·MongoDB 실행
- 성공·실패 구조화 로그와 `logrotate` 검증
- CAR·FAQ 동일 입력 2회 실행 후 중복 증가 0건 확인
- CAR 실패·FAQ 실패·Drive 실패가 서로 성공한 결과를 rollback하지 않는지 확인
- AC 결과와 evidence 경로 기록

### 2일 범위에서 연기할 항목

- 여러 자동차 기준월과 여러 FAQ 기업 동시 지원
- 실제 운영 수준 HA·DR·자동 failover·24시간 관제
- UI·API·대시보드·검색 서비스
- 복잡한 모니터링과 다중 알림 채널
- EC2 이중화와 별도 개발 환경
- 모든 장애의 자동 복구

## 7. 문서 작업 권장 순서

1. BRD 이해관계자와 목표 ID를 확정한 네 역할 기준으로 변경한다.
2. BRD의 목표·scope·제약·위험을 간소화된 최종안으로 갱신한다.
3. PRD의 단일 EC2·Docker Compose·SSM·volume 요구사항을 검토한다.
4. business key·source·schedule·로그 보존 미결 질문을 결정한다.
5. PRD의 모든 Must 요구와 AC 연결을 확인한다.
6. 요구사항 추적표를 PRD v3의 18개 Must 요구사항 기준으로 다시 작성한다.
7. Project Plan을 2일 일정과 실제 네 역할로 변경한다.
8. 문서 간 ID·owner·AC·evidence 경로가 일치하는지 검토한다.
9. 미결 질문과 `NOT_VERIFIED` 항목이 없을 때만 baseline 여부를 결정한다.

## 8. 완료 판정 체크리스트

- [ ] BRD와 PRD의 이해관계자 ID가 일치한다.
- [ ] BRD 목표 ID와 PRD의 BRD reference가 일치한다.
- [ ] 모든 Must 요구사항에 AC가 연결되어 있다.
- [ ] 모든 AC에 실행 후 생성할 evidence 경로가 있다.
- [ ] 실제 실행 전 evidence가 PASS로 표시되지 않았다.
- [ ] CAR와 FAQ의 business key가 확정됐다.
- [ ] MySQL·MongoDB 서비스·사용자·persistent volume이 분리됐다.
- [ ] 단일 EC2·Docker Compose·SSM 접근 경계가 기록됐다.
- [ ] cron·로그·logrotate 검증 기준이 정의됐다.
- [ ] credential·private endpoint·개인정보가 문서와 로그에 없다.
- [ ] Project Plan이 실제 2일 일정과 역할을 사용한다.
- [ ] 추적표의 orphan Must 요구사항이 0건이다.

## 9. 핵심 원칙 한 문장

> 자동 수집의 성공보다 더 중요한 것은, 잘못된 데이터와 불완전한 실행을 성공으로 표시하지 않고 모든 처리 결과를 다시 검증할 수 있게 남기는 것이다.

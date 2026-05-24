# 32. 감사 로그 및 운영 Summary MVP 구현 상태

작성일: 2026-05-22

## 1. 목적

운영/감사 요구사항을 이어서 구현한다. 주문, 백업, 설정 변경 등 주요 행위가 audit event로 남고, 운영 대시보드가 component 상태를 요약할 수 있도록 공통 모델과 API 골격을 추가한다.

## 2. 구현 위치

`/home/jhkim5/silver_platter/silver_platter_app`

## 3. 구현 내용

### 3.1 Audit log

추가 파일:

- `src/silver_platter/audit.py`

기능:

- audit event 모델
- append-only log helper
- action/target 기반 query
- user/session/source actor context 기록
- setting 변경 before/after diff detail 생성
- alert 확인/뮤트 audit event helper
- risk override audit event helper
- 민감정보 detail masking
- API 응답용 dict 변환

### 3.2 Operations summary

추가 파일:

- `src/silver_platter/operations.py`

기능:

- component status 모델
- 전체 상태 `ok/degraded/critical` 계산
- open issue count 계산
- provider catalog/credential/smoke 실패 상태를 component status로 변환
- 운영 대시보드용 summary dict 변환

### 3.3 Alert delivery

추가 파일:

- `src/silver_platter/alerts.py`

기능:

- operations summary의 non-ok component를 alert message로 변환
- geopolitical/realtime risk alert를 delivery message로 변환
- memory delivery provider
- webhook delivery provider와 injectable transport
- alert dispatch 결과를 audit event로 기록
- `scripts/alert_webhook_smoke` smoke

### 3.4 Repository writer

기능:

- `audit_log` insert SQL generation
- `alert_delivery_run` insert SQL generation

### 3.5 API

추가 endpoint:

- `POST /api/audit/events`
- `POST /api/audit/setting-changes`
- `GET /api/audit/events`
- `POST /api/operations/summary`
- `GET /api/operations/provider-health`
- `GET /api/providers/catalog`

## 4. 테스트

추가 테스트:

- `tests/test_audit.py`
- `tests/test_operations.py`
- `tests/test_alerts.py`

검증 범위:

- audit append/query
- target 기반 filter
- audit actor context 기록
- setting 변경 diff detail 저장
- alert 확인 audit 기록
- risk override audit 기록
- audit detail 민감정보 masking
- setting change audit API response
- operations status escalation
- provider health component mapping
- provider health license-policy detail and block state
- provider health API response
- provider catalog structured license-policy API response
- issue count 계산
- operations alert message 생성
- realtime risk alert message 생성
- delivery dispatch와 audit event 기록
- webhook transport payload 검증
- audit repository SQL generation
- alert delivery result repository SQL generation
- rollback-only repository smoke의 provider/license writer 경로
- 운영 화면 summary polling

## 5. 남은 실제 연동

- audit log 실제 Goldilocks writer smoke
  - `scripts/goldilocks_repository_smoke` 준비 완료, 기본은 rollback-only smoke opt-in 전 skip
- 실제 webhook delivery smoke는 script 준비 완료, 현재 환경은 `ALERT_WEBHOOK_URL` 없음

## 6. 검증 명령

실행 위치:

`/home/jhkim5/silver_platter/silver_platter_app`

검증 명령:

- `./scripts/lint`
- `./scripts/test`
- `./scripts/check`
- `./scripts/smoke_api`

# 29. 주문/회계/리스크 통제 MVP 구현 상태

작성일: 2026-05-22

## 1. 목적

문서 25의 Wave 3~5 범위를 이어서 구현한다. 이번 작업은 주문 preview 이후 실제 주문 흐름으로 이어지는 회계 posting, 주문 상태 전이, 멱등성, paper broker 경계, kill switch/event risk 통제를 코드와 schema에 반영하는 데 목적이 있다.

## 2. 구현 위치

`/home/jhkim5/silver_platter/silver_platter_app`

## 3. 구현 내용

### 3.1 회계/FIFO posting

수정 파일:

- `src/silver_platter/accounting.py`

추가 기능:

- execution posting 입력 모델
- transaction ledger entry 생성
- cash ledger entry 생성
- buy execution -> position lot 생성
- sell execution -> FIFO lot matching과 realized PnL 계산
- broker/internal position/cash reconciliation report

### 3.2 주문 상태기계와 멱등성

추가 파일:

- `src/silver_platter/order_state.py`

추가 기능:

- `draft -> previewed -> submitted -> accepted/filled/rejected` 상태 전이
- terminal state 보호
- invalid transition 차단
- idempotency key registry

### 3.3 Broker adapter 경계

추가 파일:

- `src/silver_platter/broker.py`
- `src/silver_platter/order_service.py`

추가 기능:

- paper broker adapter
- 한국투자증권 adapter boundary
- live order disabled 기본값
- 한국투자증권 OAuth token request mapping
- 한국투자증권 국내주식 현금주문 payload mapping
- 한국투자증권 매수가능조회/orderability query mapping
- `scripts/kis_orderable_smoke` read-only smoke
- live mode에서도 credential/transport 누락 시 broker 전송 전 rejected
- 국내주식 외 market은 broker 전송 전 rejected
- risk preview 후 broker submit
- paper adapter는 broker 전송 없이 accepted 처리
- KIS adapter는 live disabled 시 rejected 처리

### 3.4 Kill switch와 event risk

추가 파일:

- `src/silver_platter/risk_controls.py`

추가 기능:

- global/account/strategy/security kill switch 평가
- headline/global event risk signal 평가
- event signal 만료 처리
- warning/block severity 분리
- 통화별 포지션 노출 및 전체 자본 대비 비중 계산

### 3.5 API

추가 endpoint:

- `POST /api/orders/submit`

동작:

- 주문 preview 수행
- risk block이면 rejected
- idempotency 중복이면 rejected
- paper broker는 broker 미전송 accepted
- KIS broker는 live disabled 기본값으로 rejected

### 3.6 Schema

추가 migration:

- `migrations/006_order_controls_audit.sql`

추가 테이블:

- `order_state_event`
- `order_idempotency_key`
- `kill_switch_state`
- `event_risk_signal`
- `reconciliation_run`
- `audit_log`

### 3.7 Repository writer

추가 기능:

- `order_state_event` insert
- `order_idempotency_key` insert
- `audit_log` insert

## 4. 테스트

추가 테스트:

- `tests/test_accounting_posting.py`
- `tests/test_order_state.py`
- `tests/test_broker_order_service.py`
- `tests/test_risk_controls.py`

검증 범위:

- buy posting의 transaction/cash/lot 생성
- sell posting의 FIFO matching과 realized PnL
- reconciliation mismatch report
- 정상/비정상 주문 상태 전이
- idempotency duplicate 차단
- paper broker live 미전송
- KIS live disabled rejected
- KIS live mode credential/transport guard
- KIS domestic cash order OAuth/order payload mapping
- KIS orderability OAuth/query payload mapping
- KIS HTTP transport JSON POST 검증
- KIS unsupported market pre-send rejection
- order state/idempotency/audit repository SQL generation
- kill switch block
- event risk warning과 expired signal 무시
- 통화별 exposure 합산과 weight 계산

## 5. 남은 실제 연동

- Goldilocks 실제 transaction boundary smoke
- broker execution 원본 response 저장
- 주문 상태 event 실제 Goldilocks append smoke
- KIS credentials 설정 후 실제 매수가능조회 smoke
- live order 수동 승인 workflow
- kill switch UI와 audit log 조회

## 6. 검증 명령

실행 위치:

`/home/jhkim5/silver_platter/silver_platter_app`

검증 명령:

- `./scripts/lint`
- `./scripts/test`
- `./scripts/check`

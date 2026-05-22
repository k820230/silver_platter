# 25. MVP 구현 Backlog 분해

작성일: 2026-05-22  
기준 문서:

- `01_quant_auto_trading_requirements_definition_20260522.md`
- `02_overall_system_architecture_design_20260522.md`
- `04_goldilocks_initial_schema_design_20260522.md`
- `20_docker_compose_development_environment_design_20260522.md`
- `21_broker_api_integration_order_state_machine_design_20260522.md`
- `23_verification_operations_checklist_20260522.md`
- `24_open_decisions_resolution_register_20260522.md`

## 1. 목적

이 문서는 문서 단계의 요구사항을 구현 가능한 MVP backlog로 분해한다. backlog는 Epic, Story, Task, 완료 기준, 의존성, 구현 순서를 포함한다.

## 2. MVP 구현 원칙

1. 실거래보다 데이터와 리스크 통제를 먼저 구현한다.
2. 실거래 adapter는 paper/simulation 검증 이후 활성화한다.
3. Goldilocks schema와 append-only 원장을 먼저 고정한다.
4. 주문 전 risk gate는 모든 모드에서 동일하게 호출한다.
5. Web UI는 운영 화면과 주문창을 동시에 검증할 수 있을 만큼만 먼저 만든다.

## 3. Epic 목록

| Epic | 이름 | 목표 |
| --- | --- | --- |
| E-01 | 개발 환경과 프로젝트 골격 | 로컬에서 web/api/worker/scheduler 실행 |
| E-02 | Goldilocks schema와 seed | 핵심 테이블과 기본 정책 생성 |
| E-03 | 데이터 provider pipeline | 종목/가격/공시/환율 데이터 수집 골격 |
| E-04 | 계좌/원장/FIFO | 거래 원장과 손익 계산 |
| E-05 | 리스크 엔진 | 주문 전 hard gate와 warning |
| E-06 | 주문 preview와 주문 상태 | 주문창 분석, 상태 기계, paper/simulation |
| E-07 | ML/지수 계산 | 사용자 종목 예측과 위험도/변동성 지수 |
| E-08 | 사업 그룹/헤드라인/이벤트 | 그룹 리스크와 실시간 알림 |
| E-09 | Web UI | 대시보드, 주문창, 리스크, 원장 |
| E-10 | 백테스트/시뮬레이션 | replay와 가상 계좌 |
| E-11 | 백업/운영/감사 | 정기 백업, health, audit |

## 4. 구현 Wave

### Wave 0. Repository Bootstrap

목표: 실제 구현을 시작할 수 있는 최소 골격을 만든다.

| Task | 산출물 | 완료 기준 |
| --- | --- | --- |
| T-0001 | repo 구조 | `api`, `web`, `worker`, `migrations`, `docs` 디렉토리 |
| T-0002 | 공통 config | `.env.example`, config loader |
| T-0003 | Docker Compose 초안 | web/api/worker/redis, Goldilocks external 연결 |
| T-0004 | lint/test skeleton | 기본 테스트 command |
| T-0005 | health endpoint | API `/health`, worker heartbeat |

의존성: 없음

### Wave 1. Goldilocks Schema Foundation

목표: 핵심 저장 구조와 seed data를 만든다.

| Story | Task | 완료 기준 |
| --- | --- | --- |
| S-0101 Provider master | `data_provider`, `data_license` migration | provider seed 포함 |
| S-0102 Security master | `security_master`, `provider_symbol_map` | 국내/미국 구분 |
| S-0103 Market data | `price_bar`, `raw_data_manifest`, `data_quality_run` | 중복 key |
| S-0104 Event data | `disclosure_event`, `headline_event`, `global_risk_event` | headline metadata only |
| S-0105 Account ledger | `account`, `transaction_ledger`, `cash_ledger` | append-only |
| S-0106 FIFO | `position_lot`, `fifo_lot_match`, `realized_pnl` | 모든 계좌 FIFO |
| S-0107 Risk | `risk_limit`, `slippage_rule`, `risk_check_result` | 5% 유동성 한도 seed |
| S-0108 Backup | `db_backup_policy`, `db_backup_run`, `db_backup_manifest` | 토요일 10:00 KST seed |

의존성: Wave 0

### Wave 2. Data Pipeline MVP

목표: 분석과 리스크에 필요한 데이터 수집 경로를 만든다.

| Story | Task | 완료 기준 |
| --- | --- | --- |
| S-0201 Provider adapter interface | 공통 adapter protocol | mock provider test |
| S-0202 KRX/Koscom 후보 adapter | 무료 가능 데이터 수집 골격 | raw 저장 |
| S-0203 SEC EDGAR/OpenDART/KIND adapter | 공시 metadata 수집 | source id 저장 |
| S-0204 FX adapter | 환율 source placeholder | pending 상태 처리 |
| S-0205 Quality checker | 결측/중복/지연 검사 | quality run 저장 |
| S-0206 Parquet export | DuckDB 분석용 export | 날짜 파티션 |

의존성: Wave 1

### Wave 3. Accounting And FIFO

목표: 주문/체결 결과가 손익과 세금 기초 데이터로 이어지게 한다.

| Story | Task | 완료 기준 |
| --- | --- | --- |
| S-0301 Transaction posting | execution -> ledger | 원본 불변 |
| S-0302 Buy lot creation | buy -> position_lot | 잔여 수량 관리 |
| S-0303 Sell FIFO matching | sell -> fifo_lot_match | 오래된 lot 우선 |
| S-0304 Realized PnL | lot별 손익 | 수수료 배분 |
| S-0305 Overseas tax estimate input | 해외 주식 원화 환산 필드 | tax snapshot 가능 |
| S-0306 Reconciliation report | broker 잔고/현금 대사 구조 | mismatch 기록 |

의존성: Wave 1

### Wave 4. Risk Engine MVP

목표: 모든 주문 후보에 공통 risk gate를 적용한다.

| Story | Task | 완료 기준 |
| --- | --- | --- |
| S-0401 Risk rule engine | rule registry와 result model | pass/warning/block |
| S-0402 Amount limit | 100,000원~1,000,000,000원 | hard gate |
| S-0403 Auto order amount | 1건 1,000,000,000원 | hard gate |
| S-0404 Liquidity limit | 주문금액/20일 평균거래대금 <= 5% | hard gate |
| S-0405 Group liquidity limit | 그룹 당일 신규주문/그룹 평균거래대금 <= 5% | hard gate |
| S-0406 Slippage multiplier | 저유동성 3배 | warning + 비용 반영 |
| S-0407 Event risk input | 공시/headline/global event flag | warning |
| S-0408 Kill switch | global/account/strategy/security | 신규 주문 차단 |

의존성: Wave 1, Wave 2

### Wave 5. Order Preview And State Machine

목표: 주문창 preview, paper/simulation 주문 흐름, live adapter 경계를 만든다.

| Story | Task | 완료 기준 |
| --- | --- | --- |
| S-0501 Order preview API | `/api/orders/preview` | 가격/비용/리스크 |
| S-0502 Price range preview | 1D/1W/1M/3M | ML unavailable fallback |
| S-0503 Sell preview | FIFO lot 예상 소진 | 예상 손익 |
| S-0504 Tax preview | 해외 매도 예상세액 | 보조 표시 |
| S-0505 Order state machine | draft~filled/cancelled/rejected | 전이 테스트 |
| S-0506 Idempotency | 중복 주문 방지 | retry test |
| S-0507 Paper adapter | broker 미전송 | 시장 데이터 기반 체결 |
| S-0508 Korea Investment adapter skeleton | interface와 auth boundary | live disabled default |

의존성: Wave 3, Wave 4

### Wave 6. ML And Risk Index MVP

목표: 사용자 지정 종목 분석과 지수 계산을 MVP 범위로 구현한다.

| Story | Task | 완료 기준 |
| --- | --- | --- |
| S-0601 Watchlist | 사용자 지정 종목 목록 | CRUD |
| S-0602 ML job | horizon별 작업 생성 | 1D/1W/1M/3M |
| S-0603 Baseline model | linear/tree baseline | 예측 result 저장 |
| S-0604 Fine-tuning flag | 종목별 적용/미적용 사유 | 상태 저장 |
| S-0605 Prediction actual | horizon 도래 후 실제값 연결 | 오차 계산 |
| S-0606 Volatility index | EWMA V1 | 0~100 저장 |
| S-0607 Risk index | component score V1 | 0~100 저장 |
| S-0608 Chart API | 지수 시계열 조회 | UI 사용 가능 |

의존성: Wave 2, Wave 4

### Wave 7. Business Group And Event Risk

목표: 국내외 유사 사업 그룹과 headline/event risk를 연결한다.

| Story | Task | 완료 기준 |
| --- | --- | --- |
| S-0701 Business group master | taxonomy + internal group | 수동 보정 가능 |
| S-0702 Membership | security -> group | current membership |
| S-0703 Group risk metric | 노출/손실/유동성 | summary API |
| S-0704 Volatility comparison | 기준일 대비 변동 % | 복수 그룹 |
| S-0705 Headline metadata | headline+metadata only | 라이선스 안전 |
| S-0706 Global event alert | 5분 평균거래량 trigger | alert 생성 |

의존성: Wave 2, Wave 4, Wave 6

### Wave 8. Web UI MVP

목표: 사용자가 시스템 상태와 주문 위험을 확인할 수 있게 한다.

| Story | Task | 완료 기준 |
| --- | --- | --- |
| S-0801 Layout | mode/status/navigation | live/paper/simulation 명확 |
| S-0802 Dashboard | 자산/손익/위험/알림 요약 | 핵심 card/table |
| S-0803 Order ticket | preview와 risk 표시 | hard gate 버튼 비활성 |
| S-0804 Ledger view | 거래/FIFO/손익 | lot drill-down |
| S-0805 Risk dashboard | 한도/지수/이벤트 | warning/block |
| S-0806 ML screen | 예측 탭 | 모델/오차 표시 |
| S-0807 Group comparison | 변동성 비교 chart | 기준일 선택 |
| S-0808 Operations screen | data/provider/backup health | 운영 점검 |

의존성: Wave 3~7

### Wave 9. Simulation, Backtest, Operations

목표: 실거래 전 검증과 운영 감시를 닫는다.

| Story | Task | 완료 기준 |
| --- | --- | --- |
| S-0901 Virtual account | 기본 1억원 profile | reset 가능 |
| S-0902 Simulation adapter | 체결 지연/부분체결 | broker 미전송 |
| S-0903 Backtest runner | data snapshot 기반 | 미래데이터 누수 방지 |
| S-0904 Scenario tests | 시장/환율/그룹/event 충격 | 결과 저장 |
| S-0905 Backup runner | 토요일 10:00 KST | manifest/checksum |
| S-0906 Restore check | 수동 복구 검증 | report |
| S-0907 Audit log | 주문/알림/설정 변경 | 조회 가능 |
| S-0908 Go-live checklist | 23번 체크리스트 evidence | gate 상태 |

의존성: Wave 1~8

## 5. 우선순위 표

| 우선순위 | 작업 |
| --- | --- |
| P0 | Wave 0~1, Risk amount/liquidity gate, FIFO, order preview skeleton |
| P1 | Data quality, paper/simulation adapter, Web order/risk UI |
| P2 | ML baseline, volatility/risk index, group comparison |
| P3 | headline/global alert, disclosure impact prediction |
| P4 | live adapter activation, advanced tax/reporting |

## 6. MVP 완료 기준

MVP는 아래 조건을 만족할 때 완료로 본다.

- Goldilocks schema migration과 seed가 재현 가능하다.
- web/api/worker/scheduler가 local Compose로 기동된다.
- 국내+미국 종목 master와 가격 데이터 수집 경로가 있다.
- 주문 preview가 금액 한도, 유동성 5%, 저유동성 3배 슬리피지, FIFO 매도 preview를 반영한다.
- simulation 주문은 broker로 전송되지 않는다.
- paper/simulation에서 주문 상태 기계와 FIFO 손익이 검증된다.
- 종목별 변동성/위험도 지수가 0~100으로 저장되고 UI에서 조회된다.
- DB 백업 정책이 seed되고 수동 백업/manifest/checksum이 검증된다.
- 23번 체크리스트의 G1~G4 gate 증적이 남는다.

## 7. 구현 착수 직전 첫 10개 Task

1. repository 구조 생성
2. `.env.example`과 config loader 작성
3. Docker Compose dev profile 작성
4. API `/health`와 Goldilocks ping stub 작성
5. migration runner 골격 작성
6. `data_provider`, `security_master`, `price_bar` migration 작성
7. `account`, `transaction_ledger`, `position_lot`, `fifo_lot_match` migration 작성
8. `risk_limit`, `slippage_rule`, `risk_check_result` migration과 seed 작성
9. risk rule engine skeleton 작성
10. order preview API skeleton 작성

## 8. 다음 산출물

다음 문서는 `26_구현_착수_준비_및_요구사항_추적_매트릭스`로 작성한다. 이 문서에서는 구현 착수 전 gate, 문서-요구사항-backlog 추적, 검증 증적을 정리한다.

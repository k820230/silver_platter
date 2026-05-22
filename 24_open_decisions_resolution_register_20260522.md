# 24. 미결정 사항 확정 레지스터

작성일: 2026-05-22  
기준 문서:

- `01_quant_auto_trading_requirements_definition_20260522.md`
- `10_risk_engine_detailed_requirements_20260522.md`
- `11_business_group_classification_group_risk_design_20260522.md`
- `14_user_defined_security_ml_analysis_prediction_management_design_20260522.md`
- `15_security_volatility_risk_index_formula_chart_design_20260522.md`
- `17_order_ticket_realtime_price_range_pretrade_analysis_design_20260522.md`
- `18_backtest_scenario_test_detailed_requirements_20260522.md`
- `20_docker_compose_development_environment_design_20260522.md`
- `21_broker_api_integration_order_state_machine_design_20260522.md`
- `22_db_backup_restore_policy_operations_procedure_20260522.md`
- `23_verification_operations_checklist_20260522.md`

## 1. 목적

이 문서는 문서 단계 종료 후 구현 착수 전에 남은 결정사항을 하나의 레지스터로 모으고, 확정된 항목과 구현 차단 항목을 구분한다.

2026-05-22 사용자 지시에 따라 남은 미결정 사항은 구현 착수를 막지 않도록 보수적인 MVP 기본값으로 임의 확정한다. 운영 중 실제 계좌 규모와 운용 성과를 보며 versioned config로 조정한다.

결정 상태는 다음 세 가지로 관리한다.

| 상태 | 의미 |
| --- | --- |
| `confirmed` | 구현에 바로 반영 가능한 확정값 |
| `mvp_default` | 사용자 위임에 따라 보수적으로 정한 MVP 초기값 |
| `defer` | MVP 구현에는 필요 없고 후속 단계로 미룸 |

## 2. 이미 확정된 주요 결정

| ID | 항목 | 결정 | 상태 |
| --- | --- | --- | --- |
| D-001 | 초기 투자 대상 시장 | 국내+미국 동시 | confirmed |
| D-002 | 초기 실거래 증권사 API | 한국투자증권 Open API | confirmed |
| D-003 | 해외 브로커 | 별도 해외 broker API 사용 안 함 | confirmed |
| D-004 | DBMS | PostgreSQL 대신 Goldilocks 사용 | confirmed |
| D-005 | 데이터 provider | 무료 가능 조합 우선, headline은 전문 뉴스 계약 허용 | confirmed |
| D-006 | 자동 주문 가능 시간 | 거래소와 한국투자증권 API가 주문 가능으로 반환하는 모든 시간 | confirmed |
| D-007 | 자동 주문 1건 최대 금액 | 원화 환산 1,000,000,000원 | confirmed |
| D-008 | 단일 종목 투자금액 범위 | 100,000원~1,000,000,000원 | confirmed |
| D-009 | 저유동성 슬리피지 | 기준 슬리피지의 3배 | confirmed |
| D-010 | 저유동성 판정 기본 기준 | 평균 거래대금 | confirmed |
| D-011 | 종목별 유동성 한도 | 주문금액/20거래일 평균 거래대금 <= 5% | confirmed |
| D-012 | 사업 그룹 유동성 한도 | 그룹 내 당일 신규 주문금액 합계/그룹 20거래일 평균 거래대금 합계 <= 5% | confirmed |
| D-013 | 사업 그룹 분류 | 표준 산업분류 + 내부 사업 유사도 그룹 + 수동 보정 | confirmed |
| D-014 | 그룹 변동성 비교 기본 가중 | 시가총액 가중 | confirmed |
| D-015 | 그룹 구성 변경 처리 | 현재 구성 기준 | confirmed |
| D-016 | headline 저장/표시 | headline과 metadata만 저장/표시 | confirmed |
| D-017 | ML 예측 horizon | 1일, 1주, 1개월, 3개월 MVP 포함 | confirmed |
| D-018 | 종목별 ML 모델 범위 | 종목별 fine-tuning 적용 | confirmed |
| D-019 | 위험지수 표시 | 0~100 점수와 이력/추이 그래프 | confirmed |
| D-020 | 주문창 예측 horizon | 1일, 1주, 1개월, 3개월 기본, 사용자 설정 허용 | confirmed |
| D-021 | 주문창 예측 갱신 | 실시간 tick마다 preview 갱신 | confirmed |
| D-022 | FIFO 원가 계산 | 모든 계좌에 FIFO 강제 | confirmed |
| D-023 | 국제 정세 급변 이벤트 | 사건 후 5분 평균 거래량이 직전 5거래일 평균 대비 100% 이상 증가 | confirmed |
| D-024 | DB 백업 | 매주 토요일 10:00 KST | confirmed |
| D-025 | 백업 경로 | `/home/jhkim5/backup_sp/{backup_date}/` | confirmed |
| D-026 | 백업 보존/암호화 | 무한 보존, 암호화 없음 | confirmed |
| D-027 | 세금 리포트 | 단순 보조 리포트 | confirmed |
| D-028 | PC 서버 운영 | 개발용 및 장기 운영용 겸용 | confirmed |

## 3. MVP 기본값으로 확정된 항목

아래 항목은 MVP 구현 기본값으로 확정한다.

| ID | 항목 | MVP 기본값 | 구현 사용처 |
| --- | --- | --- | --- |
| M-001 | 변동성 지수 1차 산식 | EWMA 연율화 변동성, `lambda=0.94`, 252거래일 기준 | risk index, 주문창 |
| M-002 | 위험도 지수 1차 산식 | 변동성 25, 낙폭 20, 유동성 15, 이벤트 20, 그룹 10, ML 10 | risk index |
| M-003 | risk level | normal 0~20, watch 20~40, caution 40~60, danger 60~80, crisis 80~100 | UI, alert |
| M-004 | VaR confidence | 95%, 99% 병행 산출 | risk metric |
| M-005 | VaR horizon | 1D, 5D, 20D | risk metric |
| M-006 | ML 모델 MVP family | tree ensemble + baseline linear model | ML analysis |
| M-007 | 종목별 fine-tuning 최소 이력 | 일봉 2년 이상, 핵심 feature 결측 5% 이하 | ML analysis |
| M-008 | 주문창 사용자 지정 horizon 최대 | 1년 이하 | order preview |
| M-009 | 기본 preview cache TTL | 3초, tick 수신 시 즉시 무효화 | order preview |
| M-010 | 백테스트 초기 자산 | KRW 100,000,000 | backtest |
| M-011 | simulation 가상 계좌 초기 자산 | KRW 100,000,000, USD 0 | simulation |
| M-012 | simulation 체결 지연 | 기본 1초, replay에서는 bar interval 기준 | simulation |
| M-013 | simulation 부분체결 | bar 거래량의 최대 5%까지 체결 | simulation |
| M-014 | 백테스트 부분체결 제한 | bar 거래량의 최대 5% | backtest |
| M-015 | 백업 복구 검증 | 월 1회 수동 검증 | operations |
| M-016 | reconciliation 주기 | 장중 1분, 장 종료 후 1회 | broker |
| M-017 | retry 기본 | exponential backoff, idempotency key 필수 | broker |
| M-018 | 외부 모바일 접속 | MVP에서는 내부망/로컬 접속만 허용 | UI/security |

## 4. 추가 미결정 항목의 임의 확정값

아래 항목은 사용자 위임에 따라 MVP 기본값으로 확정한다.

| ID | 항목 | 확정값 | 상태 |
| --- | --- | --- | --- |
| U-001 | 단일 종목 최대 비중 | warning 5%, block 10% | mvp_default |
| U-002 | 섹터 최대 비중 | warning 25%, block 35% | mvp_default |
| U-003 | 사업 그룹 최대 비중 | warning 20%, block 30% | mvp_default |
| U-004 | 사업 그룹 최대 손실 | 일간 warning -2%, block -4%; MDD warning -8%, block -12% | mvp_default |
| U-005 | 통화별 최대 비중 | USD warning 50%, block 70%; 기타 단일 외화 block 30% | mvp_default |
| U-006 | 일일 손실 한도 | warning -1%, 신규매수 block -2%, 전체 자동주문 stop -3% | mvp_default |
| U-007 | MDD 한도 | warning -8%, 신규매수 block -12%, 전체 자동주문 stop -15% | mvp_default |
| U-008 | 저유동성 절대 하한 | 20거래일 평균 거래대금 원화 환산 1,000,000,000원 미만 | mvp_default |
| U-009 | 기본 슬리피지 bps | 한국 시장가 10bps/지정가 5bps, 미국 시장가 8bps/지정가 4bps, 저유동성 3배 | mvp_default |
| U-010 | 환율 source 우선순위 | 실제 체결은 broker 적용 환율, preview/평가는 한국투자증권 현재 환율, 세금 보조는 서울외국환중개 매매기준율, fallback 한국은행 ECOS | mvp_default |
| U-011 | 공시 영향 MVP source | OpenDART, KRX/KIND, SEC EDGAR 모두 MVP 포함 | mvp_default |
| U-012 | 공시 taxonomy | earnings, guidance, capital, M&A, contract, litigation, regulatory, buyback/dividend, ownership, listing/trading_halt, other | mvp_default |
| U-013 | 공시 가격 반응 window | D-1, D0, D+1, D+3, D+5, D+20 일봉; 분봉이 있으면 30분/1시간도 계산 | mvp_default |
| U-014 | 유사 사례 산정 방식 | 공시유형 40%, 규모/수치 surprise 25%, 종목/그룹 유사도 20%, 시장국면/변동성 15%; 최소 20건, 5~19건은 degraded | mvp_default |
| U-015 | 한국투자증권 실주문 상품/시간 | 현금계좌 국내/미국 상장 주식과 ETF만 MVP live 대상, margin/short/파생 제외, API orderable 상태가 true인 시간만 허용 | mvp_default |
| U-016 | kill switch 시 기존 open order 취소 | 기본은 신규 주문 차단만 수행, 별도 `cancel_open_orders=true` 수동 명령에서만 미체결 주문 일괄 취소 | mvp_default |
| U-017 | Goldilocks host/port | `host.docker.internal:22581`, DB `GOLDILOCKS`, schema `SP`, app user `sp_app` | mvp_default |
| U-018 | Web/API framework | API FastAPI, worker Python, Web React + Vite + TypeScript | mvp_default |
| U-019 | queue/event bus | Redis Streams를 event bus로 사용하고 RQ를 background job queue로 사용 | mvp_default |
| U-020 | scheduler | APScheduler, timezone `Asia/Seoul` | mvp_default |
| U-021 | log 보존 | application log 180일, audit log DB 영구 보존 | mvp_default |
| U-022 | backup command | `scripts/goldilocks_backup.sh` wrapper가 Goldilocks native online backup을 호출, 미지원 시 maintenance lock 후 logical export | mvp_default |
| U-023 | 복구 검증 | 월 1회 수동 복구 검증 | mvp_default |
| U-024 | backup 크기 이상 탐지 | 최근 4회 median 대비 50% 이상 증감 시 warning | mvp_default |
| U-025 | raw data 저장 루트 | `/home/jhkim5/silver_platter_data/raw`, Parquet `/home/jhkim5/silver_platter_data/parquet` | mvp_default |
| U-026 | raw data 보존 | raw 3년, canonical DB와 manifest 영구 보존 | mvp_default |
| U-027 | data quality 주문 차단 | `quality_status=risk`는 주문 preview와 자동주문 차단, `degraded`는 warning | mvp_default |
| U-028 | 모바일 접속 | MVP는 내부망 Web/PWA 조회만 허용, 모바일 신규 live 주문 비활성, 취소/알림 확인만 허용 | mvp_default |
| U-029 | global alert threshold | danger 70점 이상, crisis 85점 이상 | mvp_default |
| U-030 | 공식 확인 source 조합 | 공식 source 1개 또는 tier1 전문 뉴스 2개 이상 독립 확인 | mvp_default |
| U-031 | crisis toast 반복 | 5분 간격, 같은 event 최대 6회 | mvp_default |
| U-032 | mute 최대 시간 | danger 30분, crisis 10분 | mvp_default |
| U-033 | manual review SLA | crisis 5분, danger 15분, caution 1시간 | mvp_default |
| U-034 | delivery replay buffer | 24시간 | mvp_default |
| U-035 | 그룹 비교 최대 선택 수 | 10개 | mvp_default |
| U-036 | 기준일 휴장 처리 | 직전 유효 거래일 사용, UI에 badge 표시 | mvp_default |
| U-037 | 그룹 변동성 급등 알림 | 기준일 대비 +30% 또는 5거래일 내 +20pt | mvp_default |
| U-038 | materialized view 갱신 | 장 종료 후 1회, 장중 5분 간격 incremental | mvp_default |

## 5. MVP에서 연기할 항목

| ID | 항목 | 연기 사유 |
| --- | --- | --- |
| P-001 | 옵션 implied volatility 반영 | MVP 상품 범위 밖이며 전용 데이터 provider 계약 후 검토 |
| P-002 | 상용 뉴스 full text 저장 | 라이선스 redisplay entitlement 필요 |
| P-003 | 외부 모바일 공개 접속 | 보안/HTTPS/접근제어 설계 필요 |
| P-004 | 네이티브 모바일 앱 | Web UI 안정화 후 검토 |
| P-005 | ClickHouse/QuestDB | MVP는 Goldilocks + DuckDB/Parquet 우선 |
| P-006 | Kubernetes | 단일 PC/Docker Compose 우선 |
| P-007 | 해외 broker adapter | 한국투자증권 범위 우선 |

## 6. 구현 전 필수 확인 Gate

### 6.1 코드 작성 가능 Gate

다음 항목은 24번 결정값과 seed 기본값으로 코드 작성을 시작한다.

- 리스크 한도 테이블 구조
- 주문창 preview API
- simulation adapter
- data provider adapter 인터페이스
- schema migration 골격
- Web UI routing

### 6.2 실거래 활성화 전 검증 Gate

결정값은 모두 존재하므로 실거래 자동주문 활성화 전에는 추가 의사결정이 아니라 검증 증적이 필요하다.

- 한국투자증권 Open API orderable 상태와 실제 계좌 상품 범위 확인
- paper/simulation에서 risk gate 통과/차단 결과 확인
- kill switch 신규 주문 차단과 수동 일괄 취소 명령 확인
- 백업 1회 성공과 복구 검증 1회 성공
- 일일 손실/MDD stop이 자동 주문을 중단하는지 확인

## 7. 후속 재검토 항목

아래 항목은 MVP 운영 후 성과와 오류 데이터를 보고 조정한다.

1. 종목/섹터/사업그룹/통화별 최대 비중
2. 일일 손실과 MDD의 warning, block, stop 기준
3. 저유동성 절대 하한과 슬리피지 bps
4. 공시 유사 사례 가중치와 최소 사례 수
5. 모바일 신규 live 주문 허용 여부

## 8. 구현 반영 방식

결정값은 아래 위치에 반영한다.

| 결정 범주 | 구현 위치 |
| --- | --- |
| 한도 숫자 | `risk_limit`, seed migration |
| 슬리피지 | `slippage_rule`, order preview |
| 세금/환율 | `tax_rule_version`, FX provider config |
| 공시 taxonomy | disclosure classifier config |
| simulation 기본값 | `virtual_account_profile` seed |
| broker 정책 | broker adapter config |
| backup 정책 | `db_backup_policy` seed |

## 9. 다음 산출물

다음 문서는 `25_MVP_구현_Backlog_분해`로 작성한다. 이 문서에서는 구현 가능한 MVP 범위를 Epic, Story, Task, 완료 기준, 의존성으로 분해한다.

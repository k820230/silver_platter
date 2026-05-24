# 23. 검증/운영 체크리스트

작성일: 2026-05-22  
기준 문서:

- `01_quant_auto_trading_requirements_definition_20260522.md`
- `02_overall_system_architecture_design_20260522.md`
- `03_domain_data_model_erd_draft_20260522.md`
- `04_goldilocks_initial_schema_design_20260522.md`
- `05_data_collection_pipeline_detail_design_20260522.md`
- `06_trade_ledger_fifo_realized_pnl_design_20260522.md`
- `07_overseas_stock_capital_gains_tax_design_20260522.md`
- `08_client_realtime_test_virtual_account_simulation_design_20260522.md`
- `09_disclosure_event_impact_prediction_design_20260522.md`
- `10_risk_engine_detailed_requirements_20260522.md`
- `11_business_group_classification_group_risk_design_20260522.md`
- `12_global_headline_collection_event_risk_design_20260522.md`
- `13_global_risk_event_alert_client_exposure_design_20260522.md`
- `14_user_defined_security_ml_analysis_prediction_management_design_20260522.md`
- `15_security_volatility_risk_index_formula_chart_design_20260522.md`
- `16_business_group_volatility_comparison_chart_design_20260522.md`
- `17_order_ticket_realtime_price_range_pretrade_analysis_design_20260522.md`
- `18_backtest_scenario_test_detailed_requirements_20260522.md`
- `19_web_ui_screen_inventory_mobile_core_design_20260522.md`
- `20_docker_compose_development_environment_design_20260522.md`
- `21_broker_api_integration_order_state_machine_design_20260522.md`
- `22_db_backup_restore_policy_operations_procedure_20260522.md`

## 1. 목적

이 문서는 퀀트 기반 주식 자동매매 프로그램을 개발, 테스트, 모의운영, 제한 실거래, 장기 운영으로 전환하기 전에 확인해야 할 검증/운영 체크리스트를 정의한다.

체크리스트는 단순 기능 완료가 아니라 실제 돈이 오가는 환경에서 잘못된 주문, 데이터 오류, 리스크 누락, 백업 실패를 줄이기 위한 gate로 사용한다.

2026-05-24 기준 `[x]`는 로컬 코드, 단위 테스트, smoke script, 또는 구현 상태 문서로 확인된 항목을 뜻한다. 외부 계정, 실제 Goldilocks/Redis 인스턴스, broker credential, webhook URL이 필요한 항목은 실행 경로가 준비되어 있어도 실제 환경 검증 전까지 `[ ]`로 둔다.

## 2. 단계별 gate

| 단계 | 목적 | 다음 단계 조건 |
| --- | --- | --- |
| G1 문서/설계 완료 | 요구사항과 설계 기준 확정 | 결정 항목 목록화 |
| G2 개발 환경 준비 | 로컬 실행 가능 | Goldilocks/API/UI/worker health |
| G3 데이터 검증 | 가격/공시/헤드라인 품질 | 품질 기준 통과 |
| G4 simulation | 가상 계좌 실시간 테스트 | 주문/리스크/원장 재현 |
| G5 백테스트 | 전략과 리스크 검증 | 손실/위험 기준 충족 |
| G6 paper trading | 실시간 모의운용 | broker 미전송 보장 |
| G7 제한 실거래 | 소액/제한 전략 | kill switch와 대사 통과 |
| G8 장기 운영 | 운영 모니터링 | 백업/알림/복구 검증 |

## 3. 요구사항 체크리스트

| 항목 | 확인 |
| --- | --- |
| 국내+미국 동시 지원 범위 정의 | [x] |
| 한국투자증권 Open API 초기 broker 확정 | [x] |
| 별도 해외 broker 제외 반영 | [x] |
| Goldilocks 기준 DB 반영 | [x] |
| 자동 주문 최대 1,000,000,000원 반영 | [x] |
| 단일 종목 투자금액 100,000원~1,000,000,000원 반영 | [x] |
| 저유동성 3배 슬리피지 반영 | [x] |
| FIFO 모든 계좌 강제 반영 | [x] |
| 백업 매주 토요일 10:00 KST 반영 | [x] |
| 세금 리포트 보조 성격 표시 | [x] |

## 4. 구현 기본 결정 항목 확인

사용자 위임에 따라 구현 기본값을 확정한 항목:

| 항목 | 상태 |
| --- | --- |
| 종목별/섹터별/통화별/일일손실/MDD 리스크 한도 숫자 | [x] |
| 그룹별 최대 비중/최대 손실 | [x] |
| 변동성/위험도 지수 산식 범위 | [x] |
| 테스트 모드 기본 초기 자산/체결 지연/부분체결 정책 | [x] |
| 공시 영향 분석 MVP source/taxonomy/window | [x] |
| 환율 source 우선순위 | [x] |
| 외부 모바일 접속 방식 | [x] |
| 한국투자증권 API 실주문 가능 상품/시간 검증 | [ ] |

## 5. 개발 환경 체크리스트

| 항목 | 확인 |
| --- | --- |
| Docker Compose dev profile 기동 | [ ] |
| PostgreSQL 서비스 없음 | [x] |
| Goldilocks 연결 성공 | [ ] |
| Redis 연결 성공 | [ ] |
| API `/health` 정상 | [x] |
| Web UI 접속 가능 | [x] |
| worker heartbeat 정상 | [ ] |
| scheduler timezone `Asia/Seoul` | [x] |
| `.env` 비밀값 git 제외 | [x] |
| 로그 경로 쓰기 가능 | [ ] |

## 6. 데이터 검증 체크리스트

| 항목 | 확인 |
| --- | --- |
| 종목 master 국내/미국 구분 | [x] |
| 가격 bar 중복 방지 | [x] |
| corporate action 반영 | [x] |
| 평균 거래대금 계산 | [x] |
| 환율 데이터 수집 | [x] |
| OpenDART/KRX/KIND/SEC EDGAR 후보 연결 검토 | [x] |
| headline은 headline+metadata만 저장 | [x] |
| provider license/entitlement 기록 | [x] |
| data quality score 산출 | [x] |
| `available_to_model_at` 저장 | [x] |

## 7. ML/예측 검증 체크리스트

| 항목 | 확인 |
| --- | --- |
| 사용자 watchlist 생성 | [x] |
| 1일/1주/1개월/3개월 horizon 작업 생성 | [x] |
| 가격 예측 범위 저장 | [x] |
| 거래량 예측 저장 | [x] |
| 변동성 예측 저장 | [x] |
| 위험도 예측 저장 | [x] |
| 종목별 fine-tuning 적용/미적용 사유 저장 | [x] |
| 모델 버전과 feature set 저장 | [x] |
| 예측 실제값 매핑 | [x] |
| 예측 오차 dashboard 표시 | [x] |

## 8. 리스크 검증 체크리스트

| 항목 | 확인 |
| --- | --- |
| 단일 종목 투자금액 hard gate | [x] |
| 자동 주문 1건 최대 금액 hard gate | [x] |
| 주문금액/20거래일 평균 거래대금 5% hard gate | [x] |
| 그룹 내 당일 신규 주문금액 합계/그룹 20거래일 평균 거래대금 합계 5% hard gate | [x] |
| 저유동성 3배 슬리피지 | [x] |
| 사업 그룹 노출 계산 | [x] |
| 통화별 노출 계산 | [x] |
| 변동성 지수 산출 | [x] |
| 위험도 지수 0~100 산출 | [x] |
| 공시/헤드라인/국제 이벤트 risk signal | [x] |
| 주문 전 risk_check_result 저장 | [x] |
| kill switch 동작 | [x] |

## 9. 주문/체결 검증 체크리스트

| 항목 | 확인 |
| --- | --- |
| 주문 상태 기계 전이 테스트 | [x] |
| idempotency 중복 주문 방지 | [x] |
| 부분체결 처리 | [x] |
| 취소/정정 처리 | [x] |
| broker timeout reconciliation | [x] |
| 주문 가능 시간 확인 | [ ] |
| simulation 주문 broker 미전송 | [x] |
| paper/live 모드 명확히 분리 | [x] |
| 주문 이벤트 감사 로그 | [x] |
| broker 잔고 대사 | [x] |

## 10. 회계/FIFO/세금 검증 체크리스트

| 항목 | 확인 |
| --- | --- |
| 매수 체결 lot 생성 | [x] |
| 매도 체결 FIFO lot match | [x] |
| 실현손익 계산 | [x] |
| 미실현손익 계산 | [ ] |
| 모든 계좌 FIFO 강제 | [x] |
| 해외 주식 연간 손익 집계 | [x] |
| 예상 양도소득세 보조 표시 | [x] |
| 지방소득세 포함 표시 | [x] |
| 환율 source 기록 | [x] |
| 주문창 세금 preview와 체결 후 재계산 비교 | [ ] |

## 11. UI 검증 체크리스트

| 항목 | 확인 |
| --- | --- |
| live/paper/simulation 전역 표시 | [x] |
| 주문창 예측 가격 범위 표시 | [x] |
| 예측 데이터 오류 표시 | [ ] |
| 종목별 ML 탭 표시 | [ ] |
| 변동성/위험도 지수 차트 | [x] |
| 그룹 변동성 비교 그래프 | [x] |
| 국제 정세 급변 배너/toast/패널 | [x] |
| FIFO 매매 기록 화면 | [ ] |
| 해외 세금 화면 | [x] |
| 모바일 핵심 화면 | [x] |

## 12. 백테스트/시뮬레이션 체크리스트

| 항목 | 확인 |
| --- | --- |
| 미래 데이터 누수 방지 | [x] |
| 저유동성 슬리피지 3배 적용 | [x] |
| 리스크 엔진 동일 적용 | [x] |
| FIFO 손익 적용 | [x] |
| 시장 충격 시나리오 | [x] |
| 사업 그룹 충격 시나리오 | [x] |
| 공시/헤드라인 이벤트 시나리오 | [x] |
| replay seed 재현 | [ ] |
| 가상 계좌 초기화 | [x] |
| simulation 결과 report | [x] |

## 13. 백업/복구 체크리스트

| 항목 | 확인 |
| --- | --- |
| `/home/jhkim5/backup_sp` 존재 | [ ] |
| 백업 경로 권한 | [ ] |
| 토요일 10:00 KST schedule | [x] |
| 날짜별 폴더 생성 | [x] |
| manifest 생성 | [x] |
| checksum 생성 | [x] |
| `db_backup_run` 기록 | [ ] |
| 실패 알림 | [ ] |
| 복구 절차 문서화 | [x] |
| 복구 검증 성공 | [x] |

## 14. 보안/감사 체크리스트

| 항목 | 확인 |
| --- | --- |
| API key git 제외 | [x] |
| 실거래 권한 분리 | [x] |
| 주문 승인 audit | [x] |
| 알림 mute/확인 audit | [ ] |
| risk override audit | [ ] |
| backup 접근 권한 | [ ] |
| 외부 포트 제한 | [ ] |
| HTTPS 필요성 검토 | [ ] |
| 사용자 권한 matrix | [ ] |
| 로그 민감정보 마스킹 | [ ] |

## 15. 운영 모니터링 체크리스트

| 항목 | 확인 |
| --- | --- |
| provider 연결 상태 | [x] |
| Goldilocks health | [x] |
| Redis health | [ ] |
| worker heartbeat | [ ] |
| broker API 상태 | [ ] |
| 데이터 지연 | [ ] |
| 주문 실패 | [x] |
| 리스크 한도 위반 | [x] |
| 백업 실패 | [x] |
| 디스크 사용률 | [ ] |

## 16. 운영 전환 기준

제한 실거래 전 필수 조건:

- simulation과 paper trading에서 주문 상태, FIFO, 리스크, 백업 검증 완료
- kill switch 수동 테스트 완료
- 한국투자증권 Open API 실계좌 주문 가능 시간과 상품 검증
- 자동 주문 금액 한도 적용 확인
- 긴급 알림과 주문 차단 경로 확인
- DB 백업 1회 이상 성공과 복구 검증 완료

장기 운영 전 필수 조건:

- 2주 이상 paper/live 소액 운영 로그 검토
- 주문/체결/잔고 대사 자동화
- 알림 누락 검증
- 디스크/백업 모니터링
- MVP 리스크 한도 숫자 적용 결과 검토

## 17. 완료 증적

각 gate는 아래 증적을 남긴다.

| 증적 | 위치 |
| --- | --- |
| 테스트 결과 | test report |
| 백테스트 결과 | `backtest_run`과 report |
| simulation 결과 | `simulation_session` |
| 주문 대사 결과 | reconciliation report |
| 백업 결과 | `/home/jhkim5/backup_sp/{backup_date}`와 DB |
| 운영 승인 | audit log |
| 결정사항 반영 | 요구사항 문서 revision |

## 18. 산출물 완료 기준

본 문서까지 작성되면 요구사항 정의서의 `다음 산출물 제안` 목록 기준으로 14번 이후 남은 산출물은 모두 생성된 상태다.

후속 작업은 결정사항 반영, 구현 backlog 분해, 개발 환경 bootstrap, schema migration 작성 순서로 진행한다.

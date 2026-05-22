# 18. 백테스트/시나리오 테스트 상세 요구사항

작성일: 2026-05-22  
기준 문서:

- `01_quant_auto_trading_requirements_definition_20260522.md`
- `05_data_collection_pipeline_detail_design_20260522.md`
- `08_client_realtime_test_virtual_account_simulation_design_20260522.md`
- `10_risk_engine_detailed_requirements_20260522.md`
- `11_business_group_classification_group_risk_design_20260522.md`
- `14_user_defined_security_ml_analysis_prediction_management_design_20260522.md`

## 1. 목적

이 문서는 전략과 리스크 규칙을 실거래 전에 검증하기 위한 백테스트, 시나리오 테스트, 역스트레스 테스트, 실시간 replay 요구사항을 정의한다.

백테스트는 수익률만 검증하지 않는다. 데이터 지연, 주문 실패, 저유동성 슬리피지, 사업 그룹 동시 하락, 공시/헤드라인 이벤트, 세금과 FIFO 손익까지 포함해 실거래 전 위험을 드러내는 것이 목적이다.

## 2. 적용 범위

### 2.1 포함 범위

- 국내/미국 시장 동시 백테스트
- 전략 신호와 주문 후보 검증
- 주문 전 리스크 체크 검증
- 저유동성 종목 3배 슬리피지 반영
- 단일 종목 투자금액 한도 반영
- FIFO 손익 계산
- 해외 주식 세금 보조 계산
- 시장 충격/환율/금리/유동성/주문 실패 시나리오
- 사업 그룹 단위 충격 시나리오
- 공시/헤드라인/국제 정세 이벤트 시나리오
- 실시간 테스트 모드 replay 연동

### 2.2 제외 범위

- 실거래 주문 전송
- 외부 broker별 체결 알고리즘 완전 복제
- 네이티브 모바일 테스트 도구

## 3. 백테스트 원칙

1. 미래 데이터 누수를 금지한다.  
   모든 feature, 지수, 공시, 헤드라인은 `available_to_model_at` 기준으로만 사용한다.

2. 체결 가능성을 보수적으로 본다.  
   저유동성, 거래정지, 가격제한, 휴장, 환율 지연을 반영한다.

3. 리스크 엔진을 동일하게 사용한다.  
   실거래와 simulation, 백테스트는 같은 risk rule을 호출한다.

4. 결과는 재현 가능해야 한다.  
   데이터 snapshot, rule version, model version, 수수료/세금 설정을 저장한다.

## 4. 백테스트 실행 단위

`backtest_run` 필수 속성:

| 필드 | 설명 |
| --- | --- |
| `backtest_run_id` | 실행 식별자 |
| `strategy_id` | 전략 |
| `market_scope` | KR, US, BOTH |
| `from_date` | 시작일 |
| `to_date` | 종료일 |
| `initial_cash` | 초기 현금 |
| `currency_base` | 기준 통화 |
| `fee_rule_version` | 수수료 버전 |
| `tax_rule_version_id` | 세금 규칙 |
| `risk_rule_version` | 리스크 규칙 |
| `slippage_rule_version` | 슬리피지 규칙 |
| `data_snapshot_id` | 데이터 snapshot |
| `status` | queued, running, completed, failed |

## 5. 데이터 입력

필수 데이터:

- 가격 bar
- corporate action
- 거래량/거래대금
- 환율
- 수수료/세금 설정
- 공시 이벤트
- headline metadata
- global risk event
- business group membership
- 종목별 변동성/위험도 지수
- ML 예측 결과

대량 분석은 Goldilocks에 직접 부하를 주지 않고 DuckDB + Parquet export를 우선 사용한다.

## 6. 체결 시뮬레이션

### 6.1 기본 체결 정책

| 주문 유형 | 처리 |
| --- | --- |
| 시장가 | 다음 bar open 또는 지정 체결 모델 |
| 지정가 | bar high/low 관통 여부 확인 |
| 부분체결 | 거래량 대비 주문량 제한 |
| 미체결 | 만료 정책 적용 |

### 6.2 슬리피지

```text
if low_liquidity:
    slippage = base_slippage * 3
else:
    slippage = base_slippage
```

저유동성 판정은 평균 거래대금 기준이다.

MVP 유동성 한도는 주문금액이 해당 종목의 20거래일 평균 거래대금의 5%를 초과하지 못하도록 적용한다. 백테스트와 replay에서도 이 한도를 초과하는 주문은 실거래와 동일하게 차단한다.

### 6.3 거래량 제한

주문 체결 수량은 해당 bar 거래량의 일정 비율을 초과할 수 없다. 비율 기본값은 후속 확인 항목으로 둔다.

## 7. 리스크 엔진 검증

백테스트 중 모든 주문 후보는 리스크 엔진을 통과해야 한다.

검증 항목:

- 단일 종목 투자금액 100,000원~1,000,000,000원
- 종목/섹터/통화/사업 그룹 한도
- 현금/증거금
- 저유동성
- 변동성/위험도 지수
- 공시/헤드라인/국제 이벤트
- 중복 주문
- 주문 가능 시간

리스크 한도 숫자는 24번 결정 레지스터의 MVP 기본값을 사용하고, scenario parameter로 민감도 실험을 수행할 수 있어야 한다.

## 8. 기본 시장 시나리오

| 시나리오 | 기본 충격 |
| --- | --- |
| KOSPI 급락 | -15% |
| S&P 500 급락 | -10% |
| USD/KRW 급등 | +8% |
| 미국 10년물 금리 상승 | +100bp |
| 하이일드 스프레드 확대 | +300bp |
| VIX 급등 | 40 이상 |
| 유동성 악화 | 평균 거래대금 급감, 슬리피지 확대 |
| 주문 실패 | broker reject, timeout, partial fill |

## 9. 사업 그룹 시나리오

사업 그룹 시나리오:

- 특정 그룹 전체 -10%, -20%, -30% 하락
- 그룹 구성 종목 상관관계 1에 수렴
- 그룹 평균 거래대금 50% 감소
- 그룹 관련 부정적 headline 연속 발생
- 공식 공시/규제 이벤트 발생
- 국내외 peer 동시 하락

결과는 그룹별 손실, 한도 초과, 주문 차단, 수동 검토 발생 여부를 포함한다.

## 10. 공시/헤드라인/국제 정세 시나리오

| 이벤트 | 테스트 |
| --- | --- |
| 신규 악재 공시 | 예측 범위와 주문창 경고 |
| 정정 공시 | 기존 예측 무효화 |
| 전문 뉴스 headline | 그룹 리스크 점수 변화 |
| 국제 정세 급변 | 5분 평균 거래량이 5거래일 평균 대비 100% 이상 증가 |
| 이벤트 오보/철회 | 알림 상태 retracted |

## 11. 역스트레스 테스트

역스트레스 테스트는 전략이 깨지는 조건을 찾는다.

예시:

- 일일 손실 한도 초과에 필요한 시장 하락률
- MDD 한도 초과에 필요한 연속 손실 일수
- 사업 그룹 한도 초과에 필요한 동시 하락률
- 저유동성으로 청산 불가능해지는 거래대금 감소율
- 환율 충격으로 해외 주식 손실이 커지는 조건

결과는 숫자 threshold로 저장한다.

## 12. 결과 지표

필수 지표:

| 범주 | 지표 |
| --- | --- |
| 수익 | 누적수익률, CAGR, 평균 손익 |
| 위험 | MDD, 변동성, VaR, CVaR, beta |
| 거래 | 회전율, 승률, 평균 보유기간 |
| 비용 | 수수료, 세금, 슬리피지 비용 |
| 리스크 | 한도 위반, 주문 차단, 수동 승인 |
| 예측 | ML 예측 오차, 가격 범위 hit rate |
| 세금 | 해외 주식 예상 양도소득세 |
| 안정성 | 주문 실패, 데이터 결측 영향 |

## 13. 실시간 테스트 모드 연동

백테스트 결과는 실시간 테스트 모드의 replay seed로 사용할 수 있어야 한다.

연동 항목:

- replay 데이터 기간
- 초기 가상 자산
- 수수료/세금 정책
- 체결 지연
- 부분체결 정책
- 이벤트 주입 시각
- 주문/리스크 로그

실시간 테스트 모드 기본값은 24번 결정 레지스터의 MVP 기본값을 따른다.

## 14. API 설계

```http
POST /api/backtests
POST /api/backtests/{id}/cancel
GET /api/backtests/{id}
GET /api/backtests/{id}/results
POST /api/scenario-tests
GET /api/scenario-tests/{id}/results
```

## 15. 저장 구조

| 테이블 | 목적 |
| --- | --- |
| `backtest_run` | 백테스트 실행 |
| `backtest_order_event` | 주문 후보/전송/체결 이벤트 |
| `backtest_position_snapshot` | 포지션 snapshot |
| `backtest_metric` | 성과 지표 |
| `scenario_result` | 시나리오 테스트 결과 |
| `simulation_session` | replay 연동 세션 |

## 16. UI 요구사항

백테스트 화면:

- 실행 조건
- 성과 요약
- equity curve
- drawdown chart
- 거래 목록
- 리스크 한도 위반 이력
- 비용 breakdown
- 예측 성능
- 시나리오 결과
- replay 전환 버튼

## 17. 테스트 요구사항

| 테스트 | 검증 |
| --- | --- |
| 미래 데이터 누수 | `available_to_model_at` 기준 |
| corporate action | 수정주가 반영 |
| 저유동성 슬리피지 | 3배 적용 |
| 유동성 한도 | 주문금액/20거래일 평균 거래대금 5% 초과 차단 |
| 금액 한도 | 주문 차단 |
| FIFO 손익 | lot 매칭 |
| 해외 세금 | 보조 추정 |
| 이벤트 시나리오 | 경고/차단 |
| replay 재현 | 동일 seed 동일 결과 |

## 18. 구현 기본 결정 사항

1. 기본 초기 자산은 KRW 100,000,000, USD 0이다.
2. 부분체결 거래량 제한 비율은 bar 거래량의 5%다.
3. 수수료/세금 기본 rule version은 `fee_tax_rule_v1_mvp`다.
4. simulation replay 데이터는 3년 일봉과 가능 시 6개월 분봉을 제공한다.
5. scenario 충격값은 18번 문서의 기본 시장/그룹/event shock 값을 운영 기본값으로 사용한다.
6. 백테스트 결과는 5년 보존한다.

## 19. 다음 산출물

다음 문서는 `19_Web_UI_화면_목록과_모바일_핵심_화면_설계`로 작성한다. 해당 문서에서는 데스크톱 Web UI 화면 목록, 모바일 핵심 화면, 모드 표시, 주문/리스크/알림 화면 구성을 상세화한다.

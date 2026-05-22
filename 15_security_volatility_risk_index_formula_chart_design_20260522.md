# 15. 종목별 변동성/위험도 지수 산식 및 차트 설계서

작성일: 2026-05-22  
기준 문서:

- `01_quant_auto_trading_requirements_definition_20260522.md`
- `03_domain_data_model_erd_draft_20260522.md`
- `10_risk_engine_detailed_requirements_20260522.md`
- `14_user_defined_security_ml_analysis_prediction_management_design_20260522.md`

## 1. 목적

이 문서는 종목별 VIX 유사 변동성 지수와 0~100 위험도 지수를 산출, 저장, 시각화하는 구조를 정의한다.

개별 종목은 VIX처럼 표준화된 옵션 기반 기대 변동성 지수가 없는 경우가 많다. 따라서 MVP는 실현 변동성과 EWMA 변동성을 기반으로 내부 변동성 지수를 만들고, 위험도 지수는 변동성, 유동성, 낙폭, 이벤트 리스크, 사업 그룹 리스크를 결합한 0~100 점수로 관리한다.

## 2. 적용 범위

### 2.1 포함 범위

- 종목별 변동성 지수 산식
- 종목별 위험도 지수 산식
- 산식 버전 관리
- 시계열 저장과 재현
- 시장 지수, 사업 그룹 평균, peer 비교
- 이벤트 주석 차트
- 주문창과 리스크 엔진 연동
- 급등/괴리 알림

### 2.2 제외 범위

- 옵션 implied volatility 기반 산식 확정
- 고빈도 orderbook 변동성 모델
- 외부 상용 위험 모델 복제

옵션 implied volatility는 MVP에서 제외하고 후속 확장으로 둔다. ML 예측 변동성은 신뢰도 기준을 통과한 경우에만 위험도 구성요소로 사용한다.

## 3. 지수 설계 원칙

1. 0~100 점수로 표현한다.  
   사용자는 종목 간 위험 상태를 빠르게 비교할 수 있어야 한다.

2. 원지표와 정규화 지표를 모두 저장한다.  
   점수만 저장하면 산식 변경 시 해석이 어려워진다.

3. 산식 버전은 불변으로 관리한다.  
   과거 지수를 새 산식으로 덮어쓰지 않는다.

4. 자동 주문 직접 트리거로 사용하지 않는다.  
   주문 전 경고, risk gate 입력, 수동 검토 신호로 사용한다.

5. 결측과 비정상값을 명확히 표시한다.  
   잘못된 지수보다 `unavailable` 상태가 안전하다.

## 4. 변동성 지수 산식

### 4.1 MVP 산식

MVP 변동성 지수는 EWMA 연율화 변동성을 기준으로 계산한다.

```text
return_t = ln(close_t / close_{t-1})
ewma_var_t = lambda * ewma_var_{t-1} + (1 - lambda) * return_t^2
ewma_vol_annualized_t = sqrt(ewma_var_t) * sqrt(trading_days_per_year)
```

기본값:

| 항목 | 값 |
| --- | --- |
| `lambda` | 0.94 |
| 국내 거래일 | 252 |
| 미국 거래일 | 252 |
| 최소 관측치 | 60 거래일 |
| 보조 window | 20, 60, 120 거래일 |

### 4.2 내부 변동성 지수

원 변동성을 0~100 점수로 정규화한다.

```text
vol_percentile_t = percentile_rank(ewma_vol_t, lookback=252d)
relative_vol_t = ewma_vol_t / median(peer_group_ewma_vol_t)
vol_index_raw_t = 0.7 * vol_percentile_t + 0.3 * clamp(relative_vol_t_percentile, 0, 100)
vol_index_t = clamp(vol_index_raw_t, 0, 100)
```

해석:

| 점수 | 상태 |
| --- | --- |
| 0~20 | 낮음 |
| 20~40 | 안정 |
| 40~60 | 보통 |
| 60~80 | 경계 |
| 80~100 | 급등/위험 |

### 4.3 입력 데이터

| 입력 | 사용 |
| --- | --- |
| `price_bar.close` | 수익률 계산 |
| `price_bar.high/low` | range 기반 보조 변동성 |
| `price_bar.volume` | 거래량 급증 보조 판단 |
| `business_group_member` | peer group 비교 |
| `market_index_bar` | 시장 대비 변동성 비교 |
| `ml_prediction_result` | 후속 확장 시 예측 변동성 입력 |

## 5. 위험도 지수 산식

### 5.1 위험도 구성요소

위험도 지수는 0~100 점수로 산출한다.

| 구성요소 | 기본 가중치 | 설명 |
| --- | ---: | --- |
| 변동성 점수 | 25 | 종목별 변동성 지수 |
| 낙폭 점수 | 20 | 최근 MDD, 회복 지연 |
| 유동성 점수 | 15 | 평균 거래대금, 스프레드 proxy |
| 이벤트 점수 | 20 | 공시/헤드라인/국제 정세 |
| 사업 그룹 점수 | 10 | 그룹 리스크와 동시 하락 |
| ML 위험 예측 | 10 | 사용자 지정 종목 ML 위험도 |

```text
risk_index =
  0.25 * volatility_score
+ 0.20 * drawdown_score
+ 0.15 * liquidity_risk_score
+ 0.20 * event_risk_score
+ 0.10 * business_group_risk_score
+ 0.10 * ml_risk_score
```

MVP에서 ML 위험 예측이 없거나 신뢰도가 낮으면 해당 가중치를 나머지 구성요소에 비례 배분한다.

### 5.2 낙폭 점수

```text
drawdown = (close_t / rolling_max_close_252d) - 1
drawdown_score = percentile_or_scaled(abs(drawdown), market_scope)
```

회복 기간이 길거나 저점 갱신이 반복되면 가산한다.

### 5.3 유동성 점수

저유동성 판정은 평균 거래대금 기준이다.

```text
turnover_ratio = order_amount_krw / avg_daily_turnover_20d_krw
liquidity_risk_score = f(avg_daily_turnover_20d_krw, turnover_ratio)
```

저유동성 종목은 주문창과 리스크 엔진에서 기준 슬리피지의 3배를 적용한다.

### 5.4 이벤트 점수

이벤트 점수 입력:

- 신규 공시 영향 예측
- 사업 그룹 headline risk signal
- 국제 정세 급변 이벤트
- 거래정지, 투자주의, 규제 이벤트

공식 확인된 이벤트와 전문 뉴스 계약 source는 높은 신뢰도로 반영한다. 헤드라인 저장/표시는 headline과 metadata만 사용한다.

## 6. 산식 버전 관리

`risk_index_formula_version`은 지수 산식의 불변 기준이다.

| 필드 | 설명 |
| --- | --- |
| `formula_version_id` | 산식 버전 |
| `formula_code` | VOL_EWMA_V1, RISK_SCORE_V1 |
| `formula_type` | volatility, risk |
| `input_spec_json` | 입력 데이터 정의 |
| `weight_spec_json` | 가중치 정의 |
| `normalization_spec_json` | 정규화 방식 |
| `valid_from` | 적용 시작 |
| `valid_to` | 적용 종료 |
| `status` | candidate, active, retired |

산식 버전이 바뀌면 새 지수 row를 생성한다. 기존 row는 수정하지 않는다.

## 7. 저장 구조

### 7.1 변동성 지수

`security_volatility_index`:

| 필드 | 설명 |
| --- | --- |
| `security_id` | 종목 |
| `index_ts` | 지수 기준 시각 |
| `formula_version_id` | 산식 버전 |
| `raw_volatility` | EWMA 연율화 변동성 |
| `volatility_index` | 0~100 지수 |
| `peer_relative_value` | peer 대비 값 |
| `market_relative_value` | 시장 대비 값 |
| `quality_status` | ok, degraded, unavailable |

### 7.2 위험도 지수

`security_risk_index`:

| 필드 | 설명 |
| --- | --- |
| `security_id` | 종목 |
| `index_ts` | 지수 기준 시각 |
| `formula_version_id` | 산식 버전 |
| `risk_score` | 0~100 |
| `risk_level` | normal, watch, caution, danger, crisis |
| `component_scores_json` | 구성요소별 점수 |
| `driver_json` | 주요 위험 요인 |
| `quality_status` | ok, degraded, unavailable |

## 8. 지수 계산 흐름

```text
price_bar 적재
  -> 수익률 계산
  -> EWMA 변동성 산출
  -> peer/시장 대비 정규화
  -> security_volatility_index 저장
  -> 낙폭/유동성/이벤트/그룹/ML 점수 결합
  -> security_risk_index 저장
  -> 알림/주문창/리스크 엔진 publish
```

## 9. 차트 설계

### 9.1 종목 상세 차트

필수 차트:

| 차트 | 내용 |
| --- | --- |
| 변동성 지수 추이 | 0~100 지수, 장기 평균, threshold |
| 위험도 지수 추이 | 0~100 점수와 risk level |
| 가격/거래량 overlay | 지수 급등 시 가격/거래량 변화 |
| peer 비교 | 사업 그룹 평균, peer 종목 |
| 이벤트 주석 | 공시, headline, 국제 정세 이벤트 |

### 9.2 차트 표시 원칙

- x축은 거래일 기준과 실제 시각 기준을 선택할 수 있어야 한다.
- 결측 구간은 선을 이어서 오해를 만들지 않는다.
- 지수 산식 버전을 표시한다.
- 산식 변경 시 차트에 버전 변경 marker를 표시한다.
- risk level 색상은 전 화면에서 동일하게 사용한다.

### 9.3 위험 level 색상

| level | 점수 | UI 의미 |
| --- | ---: | --- |
| normal | 0~20 | 정상 |
| watch | 20~40 | 관찰 |
| caution | 40~60 | 주의 |
| danger | 60~80 | 위험 |
| crisis | 80~100 | 위기 |

## 10. 알림 규칙

알림 후보:

- 변동성 지수가 80 이상
- 위험도 지수가 80 이상
- 변동성 지수가 5거래일 내 30점 이상 상승
- 위험도 지수가 사업 그룹 평균보다 2표준편차 이상 높음
- 장기 평균 대비 급격한 이탈
- 공시/헤드라인 이벤트 이후 지수 급등

알림은 자동 주문을 직접 발생시키지 않는다. 주문창 경고, 리스크 대시보드, 수동 검토 queue로 전달한다.

## 11. 주문창 연동

주문창은 다음 값을 사용한다.

| 값 | 사용 |
| --- | --- |
| 현재 변동성 지수 | 기간별 예상 가격 범위 폭 조정 |
| 위험도 지수 | 주문 전 위험 경고 |
| risk level | 수동 확인 요구 |
| 유동성 점수 | 슬리피지와 체결 불확실성 |
| 이벤트 driver | 주문 전 경고 문구 |

위험도 지수가 `danger` 이상이면 주문창은 예측 가격 범위와 함께 경고를 표시하고 수동 확인을 요구한다.

## 12. 리스크 엔진 연동

리스크 엔진 입력:

- `security_volatility_index.latest`
- `security_risk_index.latest`
- risk level threshold
- 지수 변화율
- peer 괴리

hard gate 여부는 24번 결정 레지스터의 종목별/섹터별/통화별/일일손실/MDD 한도 숫자와 지수 threshold를 결합해 결정한다.

## 13. 데이터 품질

| 문제 | 처리 |
| --- | --- |
| 가격 결측 | 해당 일자 지수 unavailable |
| 거래정지 | 별도 상태 표시, 변동성 계산 제외 또는 고정 |
| 상장 초기 종목 | 최소 관측치 전까지 degraded |
| 주식분할/병합 미반영 | corporate action 조정 전 계산 차단 |
| peer group 없음 | 시장 대비 정규화만 사용 |
| 이벤트 매핑 불확실 | event score confidence 낮춤 |

## 14. 테스트 요구사항

| 테스트 | 검증 |
| --- | --- |
| EWMA 재현성 | 동일 입력 동일 지수 |
| 산식 버전 불변성 | 기존 지수 overwrite 금지 |
| 결측 처리 | unavailable/degraded 분기 |
| peer 비교 | 사업 그룹 평균 계산 검증 |
| 0~100 clamp | 점수 범위 보장 |
| 이벤트 주석 | 공시/헤드라인 marker 연결 |
| 주문창 전달 | 최신 지수 조회와 경고 표시 |

## 15. 구현 기본 결정 사항

1. MVP 변동성 산식은 EWMA V1로 시작하고 옵션 implied volatility는 제외한다.
2. EWMA lambda는 0.94, lookback window는 252거래일이다.
3. 위험도 구성요소 가중치는 변동성 25, 낙폭 20, 유동성 15, 이벤트 20, 그룹 10, ML 10이다.
4. alert 기준은 danger 70점 이상, crisis 85점 이상이다.
5. peer 비교 우선순위는 수동 peer, 내부 사업 그룹, 표준 산업분류 순이다.
6. 장중 지수는 5분 간격 incremental, 장 종료 후 full recompute로 갱신한다.

## 16. 다음 산출물

다음 문서는 `16_사업_그룹_변동성_비교_그래프_설계서`로 작성한다. 해당 문서에서는 사용자가 선택한 여러 사업 그룹의 기준일 대비 변동성 변동률을 하나의 그래프로 비교하는 기능을 상세화한다.

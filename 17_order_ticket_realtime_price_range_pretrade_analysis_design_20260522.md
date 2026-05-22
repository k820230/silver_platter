# 17. 주문창 실시간 예측 주가 범위 및 주문 전 분석 설계서

작성일: 2026-05-22  
기준 문서:

- `01_quant_auto_trading_requirements_definition_20260522.md`
- `06_trade_ledger_fifo_realized_pnl_design_20260522.md`
- `07_overseas_stock_capital_gains_tax_design_20260522.md`
- `10_risk_engine_detailed_requirements_20260522.md`
- `14_user_defined_security_ml_analysis_prediction_management_design_20260522.md`
- `15_security_volatility_risk_index_formula_chart_design_20260522.md`

## 1. 목적

이 문서는 주문창에서 사용자가 현재 거래가격으로 매수 또는 매도할 때, 기간별 예상 주가 범위, 예상 손익, 수수료/세금, 슬리피지, 리스크 한도 영향을 실시간으로 계산해 보여주는 구조를 정의한다.

## 2. 적용 범위

### 2.1 포함 범위

- 국내와 미국 주식 주문창
- 한국투자증권 Open API 주문 가능 시간 연동
- 1일, 1주, 1개월, 3개월 기본 horizon
- 사용자 지정 horizon
- 실시간 tick마다 preview 갱신
- 단일 종목 투자금액 100,000원~1,000,000,000원 제한
- 저유동성 종목 3배 슬리피지 적용
- FIFO 매도 예상 손익
- 해외 주식 예상 양도소득세 보조 표시
- 리스크 체크와 주문 전 경고

### 2.2 제외 범위

- 실제 주문 상태 기계 상세
- 브로커 API field mapping 상세
- 모바일 native 주문창

## 3. 설계 원칙

1. 주문 전 preview와 실제 체결 결과를 분리한다.  
   주문창 값은 가정 기반이며, 체결 후 원장과 세금은 실제 체결 데이터로 다시 계산한다.

2. tick마다 계산하지만 모델 재학습은 하지 않는다.  
   실시간 갱신은 현재가, 주문금액, 슬리피지, 리스크 상태를 재계산하는 것이다.

3. 위험한 예측은 표시하지 않는다.  
   데이터 지연, 모델 오류, 품질 저하 상태에서는 가격 범위 표시를 중단하고 사유를 보여준다.

4. hard gate와 warning을 구분한다.  
   투자금액 한도, 주문 가능 시간, 현금 부족 등은 hard gate이고 예측 불확실성은 warning 또는 수동 확인이다.

## 4. 주문창 입력

| 입력 | 설명 |
| --- | --- |
| `account_id` | 실계좌, paper, simulation |
| `security_id` | 종목 |
| `side` | buy, sell |
| `order_type` | market, limit 등 |
| `price` | 현재가 또는 지정가 |
| `quantity` | 주문 수량 |
| `order_amount_krw` | 원화 환산 주문금액 |
| `horizons` | 기본 1d, 1w, 1m, 3m |
| `mode` | live, paper, simulation |

## 5. 실시간 preview 계산 흐름

```text
주문 입력 변경 또는 tick 수신
  -> 현재가/환율/수수료/세금 조회
  -> 주문금액 원화 환산
  -> 단일 종목 금액 한도 검사
  -> 평균 거래대금 기반 저유동성 판정
  -> 슬리피지 산출
  -> 최신 ML 예측 조회
  -> 변동성/위험도 지수 조회
  -> horizon별 예상 가격 범위 보정
  -> 예상 손익/손실확률 계산
  -> 리스크 엔진 preview check
  -> 주문창 표시
```

## 6. 투자금액 한도

단일 종목 주문 후 투자금액은 원화 환산 기준 아래 범위에 있어야 한다.

| 항목 | 값 |
| --- | ---: |
| 최소 투자금액 | 100,000원 |
| 최대 투자금액 | 1,000,000,000원 |

검사 기준:

- 신규 매수 주문은 주문금액 기준
- 추가 매수 주문은 주문 후 총 보유금액 기준
- 미국 주식은 적용 환율로 원화 환산
- simulation도 동일 규칙 적용

한도 위반은 주문 생성 또는 전송을 차단한다.

## 7. 슬리피지 산출

### 7.1 기본 슬리피지

기본 슬리피지는 종목, 시장, 주문유형, 평균 거래대금, 스프레드 proxy로 산출한다.

```text
base_slippage_bps = market_base_bps + liquidity_adjustment_bps + order_size_impact_bps
```

### 7.2 저유동성 3배 규칙

저유동성 판정은 평균 거래대금 기준이다.

```text
if avg_daily_turnover_20d_krw < low_liquidity_turnover_threshold:
    applied_slippage_bps = base_slippage_bps * 3
else:
    applied_slippage_bps = base_slippage_bps
```

MVP 유동성 hard gate는 주문금액이 해당 종목의 20거래일 평균 거래대금의 5%를 초과하는지 검사한다.

```text
if order_amount_krw / avg_daily_turnover_20d_krw > 0.05:
    block_order("LIQUIDITY_LIMIT_EXCEEDED")
```

주문창에는 "평균 거래대금 기준 저유동성 종목으로 기준 슬리피지의 3배 적용"을 명확히 표시한다.

## 8. horizon별 가격 범위

### 8.1 기본 horizon

MVP 기본 horizon:

- 1일
- 1주
- 1개월
- 3개월

사용자 지정 horizon은 별도 입력으로 허용하되, 모델 예측이 없으면 변동성 기반 범위만 표시한다.

### 8.2 가격 범위 계산

ML 예측이 정상일 때:

```text
adjusted_lower = ml_price_lower - expected_cost_per_share - slippage_cost_per_share
adjusted_median = ml_price_median - expected_cost_per_share
adjusted_upper = ml_price_upper - expected_cost_per_share + favorable_slippage_bound
```

ML 예측이 unavailable일 때:

```text
vol_range = current_price * expected_volatility * sqrt(horizon_days / 252)
lower = current_price - z_value * vol_range
median = current_price
upper = current_price + z_value * vol_range
```

### 8.3 표시값

| 값 | 설명 |
| --- | --- |
| 예상 하한 | 비용/슬리피지 반영 후 하단 가격 |
| 예상 중앙값 | 기준 경로 |
| 예상 상한 | 상단 가격 |
| 예상 손익 하한 | 주문 수량 기준 손익 하한 |
| 예상 손익 중앙값 | 중앙 손익 |
| 예상 손익 상한 | 상단 손익 |
| 손실 확률 | 가격 예측과 변동성 기반 |
| 신뢰도 | 모델 confidence와 데이터 품질 |

## 9. 매수 주문 preview

매수 preview 표시:

- 주문금액
- 예상 수수료와 세금
- 예상 슬리피지
- 총 매입 가정 금액
- horizon별 예상 가격 범위
- horizon별 예상 손익 범위
- 단일 종목 투자금액 한도 상태
- 사업 그룹/섹터/통화 한도 영향
- 종목별 변동성/위험도 지수
- 관련 공시/헤드라인/국제 이벤트 경고

## 10. 매도 주문 preview

매도 preview는 FIFO lot matching을 가정한다.

표시 항목:

- 매도 수량이 소진할 매수 lot 목록
- lot별 매입일, 매입가, 잔여 수량
- lot별 예상 매도금액
- lot별 예상 실현손익
- 총 예상 실현손익
- 수수료/세금
- 해외 주식이면 해당 연도 예상 양도소득세 변화

FIFO는 모든 계좌에 강제 적용한다.

## 11. 해외 주식 세금 preview

미국 주식 매도 주문창에는 보조 정보로 표시한다.

| 표시 | 설명 |
| --- | --- |
| 연간 실현손익 | 현재까지 해당 연도 합산 |
| 이번 주문 가정 손익 | FIFO 기준 |
| 예상 과세표준 변화 | 기본공제 반영 전/후 |
| 예상 세액 변화 | 지방소득세 포함 표시 |
| 적용 환율 상태 | source와 기준일 |
| 신고 자료 수준 | 단순 보조 리포트 |

세금 정보는 신고 확정 자료가 아니라 보조 추정치로 표시한다.

## 12. 리스크 체크

주문창 preview는 리스크 엔진의 사전 체크를 호출한다.

| 체크 | 실패 시 |
| --- | --- |
| 주문 가능 시간 | 전송 차단 |
| 투자금액 한도 | 생성/전송 차단 |
| 현금/증거금 | 전송 차단 |
| 저유동성 | 경고 또는 수동 확인 |
| 사업 그룹 한도 | 차단 또는 수동 승인 |
| 위험도 지수 | 경고 또는 수동 확인 |
| 공시/뉴스 이벤트 | 경고 |
| 중복 주문 | 전송 차단 |
| broker 장애 | 전송 차단 |

리스크 한도 숫자는 후속 확인 후 hard gate threshold에 반영한다.

## 13. API 설계

```http
POST /api/orders/preview
```

요청:

```json
{
  "account_id": 10,
  "security_id": 1001,
  "side": "buy",
  "order_type": "limit",
  "price": 72000,
  "quantity": 10,
  "horizons": ["1d", "1w", "1m", "3m"],
  "mode": "live"
}
```

응답:

```json
{
  "preview_id": "op_20260522_0001",
  "order_amount_krw": 720000,
  "amount_limit_status": "ok",
  "slippage": {
    "base_bps": 12,
    "applied_bps": 36,
    "low_liquidity_multiplier": 3
  },
  "price_ranges": [
    {
      "horizon": "1w",
      "lower": 69500,
      "median": 72500,
      "upper": 75800,
      "prob_loss": 0.42
    }
  ],
  "risk_check": {
    "status": "warning",
    "warnings": ["LOW_LIQUIDITY"]
  }
}
```

## 14. 실시간 갱신

갱신 트리거:

- 실시간 tick 수신
- 주문 가격/수량 변경
- 환율 변경
- 수수료 정책 변경
- 변동성/위험도 지수 변경
- 신규 공시/헤드라인/국제 이벤트 발생
- 모델 예측 결과 갱신

tick마다 전체 모델 계산을 다시 수행하지 않고, 최신 예측 결과를 현재가 기준으로 재보정한다.

## 15. UI 상태

| 상태 | 표시 |
| --- | --- |
| 정상 | 가격 범위와 리스크 요약 |
| 데이터 지연 | 예측 표시 중단 또는 degraded |
| 모델 오류 | 모델 오류 badge와 변동성 기반 fallback |
| 한도 위반 | 전송 버튼 비활성 |
| 수동 확인 필요 | 확인 checkbox와 감사 로그 |
| simulation | 화면 전체에 simulation 표시 |

## 16. 감사 로그

기록 대상:

- preview 생성
- 경고 표시
- 수동 확인
- 한도 위반
- 주문 전송 시 preview id 연결
- prediction/risk index 버전
- 세금 preview 표시

## 17. 테스트 요구사항

| 테스트 | 검증 |
| --- | --- |
| 금액 한도 | 100,000원 미만/1,000,000,000원 초과 차단 |
| 저유동성 | 3배 슬리피지 적용 |
| tick 갱신 | 가격 범위 재계산 |
| ML unavailable | fallback 또는 표시 중단 |
| 매도 FIFO | lot별 예상 손익 |
| 해외 세금 | 연간 예상세액 변화 |
| simulation | 실제 broker 미전송 |
| 리스크 경고 | 수동 확인과 감사 로그 |

## 18. 구현 기본 결정 사항

1. 평균 거래대금 기준 저유동성 절대 하한은 20거래일 평균 거래대금 원화 환산 1,000,000,000원 미만이다.
2. 기본 슬리피지는 한국 시장가 10bps/지정가 5bps, 미국 시장가 8bps/지정가 4bps다.
3. 사용자 지정 horizon 최대 기간은 1년이다.
4. 주문창 preview cache TTL은 3초이며 tick 수신 시 즉시 무효화한다.
5. danger 이상 위험도, 공시 예상 하락 하한 -5% 이하, 유동성 degraded, 환율 pending은 수동 확인 warning으로 둔다.
6. 환율 source 우선순위는 broker 적용 환율, 한국투자증권 현재 환율, 서울외국환중개, 한국은행 ECOS 순이다.

## 19. 다음 산출물

다음 문서는 `18_백테스트_시나리오_테스트_상세_요구사항`으로 작성한다. 해당 문서에서는 전략 백테스트, 실시간 replay, 시장 충격/데이터 장애/주문 실패 시나리오, 결과 검증 지표를 상세화한다.

# 16. 사업 그룹 변동성 비교 그래프 설계서

작성일: 2026-05-22  
기준 문서:

- `01_quant_auto_trading_requirements_definition_20260522.md`
- `03_domain_data_model_erd_draft_20260522.md`
- `11_business_group_classification_group_risk_design_20260522.md`
- `15_security_volatility_risk_index_formula_chart_design_20260522.md`

## 1. 목적

이 문서는 사용자가 종목 그룹 리스트에서 여러 사업 그룹을 선택하고, 지정 기준일의 그룹 변동성값을 기준으로 각 그룹의 변동성 변동률을 하나의 그래프에서 비교하는 기능을 정의한다.

## 2. 적용 범위

### 2.1 포함 범위

- 복수 사업 그룹 선택
- 기준일 선택
- 기준일 대비 변동성 변동률 계산
- 시가총액 가중 기본 방식
- 현재 구성 기준 그룹 멤버십 적용
- 가중 방식 변경
- 결측/비정상 기준값 처리
- 차트와 테이블 표시
- 리스크 대시보드 연동

### 2.2 제외 범위

- 사업 그룹 자동 분류 모델 상세
- 개별 종목 peer 차트 상세
- 외부 모바일 전용 UI 상세

## 3. 핵심 결정 사항

| 항목 | 결정 |
| --- | --- |
| 그룹 분류 기준 | 표준 산업분류 + 내부 사업 유사도 그룹 + 수동 보정 병행 |
| 기본 가중 방식 | 시가총액 가중 |
| 구성 변경 처리 | 현재 구성 기준 |
| 비교 지표 | 기준일 대비 변동성 변동 % |
| 기준값 | 사용자가 지정한 기준일의 그룹 변동성 |

## 4. 사용자 흐름

```text
사업 그룹 리스트 진입
  -> 비교할 그룹 다중 선택
  -> 기준일 선택
  -> 비교 기간 선택
  -> 가중 방식 확인 또는 변경
  -> 변동성 변동 % 그래프 표시
  -> 이상 그룹 drill-down
```

## 5. 그룹 변동성 산식

### 5.1 종목 변동성 입력

기본 입력은 `security_volatility_index.raw_volatility` 또는 `volatility_index`다.

MVP 비교에는 원 변동성 기반 그룹 변동성을 사용하고, UI에는 0~100 지수 비교도 보조로 제공한다.

### 5.2 시가총액 가중 그룹 변동성

```text
weight_i_t = market_cap_i_t / sum(market_cap_j_t)
group_vol_t = sum(weight_i_t * security_vol_i_t)
```

시가총액 결측 종목은 아래 순서로 처리한다.

1. 최근 유효 시가총액 사용
2. 결측이 오래된 경우 동일 가중 fallback
3. fallback 발생 사실을 quality flag로 표시

### 5.3 대체 가중 방식

| 방식 | 설명 | 사용 |
| --- | --- | --- |
| `market_cap_weight` | 시가총액 가중 | 기본 |
| `equal_weight` | 동일 가중 | 시가총액 결측 보조 |
| `portfolio_weight` | 사용자 보유 비중 가중 | 포트폴리오 영향 분석 |

## 6. 기준일 정규화

사용자가 선택한 기준일의 그룹 변동성을 기준값으로 사용한다.

```text
base_group_vol = group_vol(base_date)
vol_change_pct_t = ((group_vol_t / base_group_vol) - 1) * 100
```

기준값 처리:

| 조건 | 처리 |
| --- | --- |
| 기준값 정상 | 변동 % 계산 |
| 기준값 0 | 비교 제외, 경고 표시 |
| 기준값 결측 | 가장 가까운 이전 유효 거래일 사용 여부를 사용자에게 표시 |
| 기준값 비정상 spike | 품질 경고, 기준일 변경 제안 |

## 7. 그룹 구성 기준

MVP 기본은 현재 구성 기준이다.

| 기준 | 설명 |
| --- | --- |
| 현재 구성 | 현재 사업 그룹 구성 종목을 과거 기간 전체에 적용 |
| 당시 구성 | 각 일자의 point-in-time 구성 사용 |
| 고정 구성 | 사용자가 선택 시점의 구성 고정 |

현재 구성 기준은 사용자가 지금 보는 그룹을 비교하기 쉽지만, 과거 구성 변경의 survivorship bias가 생길 수 있다. UI에는 구성 기준을 명시한다.

## 8. 데이터 모델

### 8.1 그룹 변동성 지수

`business_group_volatility_index`:

| 필드 | 설명 |
| --- | --- |
| `business_group_id` | 사업 그룹 |
| `index_ts` | 기준 시각 |
| `formula_version_id` | 산식 버전 |
| `weight_method` | market_cap_weight 등 |
| `membership_basis` | current, point_in_time, fixed |
| `group_volatility` | 그룹 변동성 |
| `member_count` | 포함 종목 수 |
| `coverage_ratio` | 계산 가능 종목 비율 |
| `quality_status` | ok, degraded, unavailable |

### 8.2 비교 view

`business_group_volatility_compare_view`:

| 필드 | 설명 |
| --- | --- |
| `comparison_id` | 비교 요청 |
| `business_group_id` | 그룹 |
| `base_date` | 기준일 |
| `base_volatility` | 기준 변동성 |
| `compare_date` | 비교일 |
| `current_volatility` | 비교일 변동성 |
| `vol_change_pct` | 변동률 |
| `formula_version_id` | 산식 버전 |
| `weight_method` | 가중 방식 |
| `membership_basis` | 구성 기준 |

## 9. API 설계

### 9.1 비교 요청

```http
POST /api/business-groups/volatility-comparison
```

요청:

```json
{
  "business_group_ids": [101, 102, 103],
  "base_date": "2026-05-01",
  "from_date": "2026-05-01",
  "to_date": "2026-05-22",
  "weight_method": "market_cap_weight",
  "membership_basis": "current",
  "formula_version": "VOL_EWMA_V1"
}
```

응답:

```json
{
  "base_date": "2026-05-01",
  "series": [
    {
      "business_group_id": 101,
      "business_group_name": "반도체",
      "base_volatility": 0.32,
      "points": [
        {"date": "2026-05-01", "vol_change_pct": 0.0},
        {"date": "2026-05-22", "vol_change_pct": 18.7}
      ],
      "quality_status": "ok"
    }
  ]
}
```

## 10. UI 설계

### 10.1 그룹 리스트

그룹 리스트 필수 표시:

- 그룹명
- 표준 산업분류
- 내부 사업 유사도 그룹명
- 구성 종목 수
- 국내/미국 종목 수
- 현재 그룹 변동성
- 위험도 점수
- 최근 headline/event count
- 비교 선택 checkbox

### 10.2 비교 그래프

그래프 필수 요소:

| 요소 | 설명 |
| --- | --- |
| y축 | 기준일 대비 변동성 변동 % |
| x축 | 날짜/시각 |
| series | 선택한 사업 그룹 |
| 기준선 | 0% |
| tooltip | 기준 변동성, 현재 변동성, 변동 %, 가중 방식 |
| badge | 산식 버전, 구성 기준 |
| marker | 주요 공시/헤드라인/국제 이벤트 |

### 10.3 상호작용

- 그룹 추가/제거
- 기준일 변경
- 기간 변경
- 가중 방식 변경
- 구성 기준 변경
- 특정 그룹 숨김/표시
- 차트에서 특정 날짜 클릭 시 해당 그룹의 구성 종목 변동성 drill-down

## 11. 리스크 연동

그룹 변동성 비교는 다음 판단에 사용한다.

- 특정 사업 그룹의 변동성 급등
- 여러 그룹 동시 변동성 확대
- 포트폴리오 보유 그룹과 시장 관심 그룹 비교
- 신규 주문 후 노출될 그룹의 최근 위험 상태 확인
- 국제 정세 이벤트 영향 그룹 탐지

그룹 변동성 급등은 자동 주문 직접 트리거가 아니며, 주문창 경고와 리스크 대시보드 알림에 사용한다.

## 12. 결측과 품질 처리

| 상황 | 처리 |
| --- | --- |
| 그룹 구성 종목 없음 | 비교 불가 |
| 종목 변동성 결측 과다 | degraded |
| 기준일 휴장 | 직전 거래일 사용 여부 표시 |
| 기준값 0/비정상 | 비교 제외 |
| 시가총액 결측 | fallback 또는 제외 |
| 통화 혼합 | 변동성은 무차원 비율로 계산, 금액 가중 시 원화 환산 |

## 13. 성능 요구사항

- 사용자가 10개 그룹, 1년 일봉 기간을 선택해도 2초 이내 응답을 목표로 한다.
- 일별 그룹 변동성은 사전 계산한다.
- 장중 비교는 최근 지수 변경분만 incremental 계산한다.
- 장기 기간 조회는 materialized view 또는 cache를 사용한다.

## 14. 테스트 요구사항

| 테스트 | 검증 |
| --- | --- |
| 기준일 정규화 | 0% 시작 검증 |
| 기준값 결측 | fallback 표시 |
| 시가총액 가중 | 가중합 검증 |
| 현재 구성 기준 | 현재 멤버십 적용 |
| 그룹 추가/삭제 | series 반영 |
| 이벤트 marker | 관련 headline/disclosure 연결 |
| 품질 flag | degraded/unavailable 표시 |

## 15. 구현 기본 결정 사항

1. 그룹별 최대 비교 선택 수는 10개다.
2. 기준일이 휴장일이면 직전 유효 거래일을 사용하고 UI에 badge를 표시한다.
3. 변동성 급등 알림은 기준일 대비 +30% 또는 5거래일 내 +20pt 상승으로 둔다.
4. materialized view는 장 종료 후 1회, 장중 5분 간격 incremental로 갱신한다.
5. 포트폴리오 보유 비중 가중은 MVP에서 조회 옵션으로만 제공하고 기본값은 시가총액 가중이다.

## 16. 다음 산출물

다음 문서는 `17_주문창_실시간_예측_주가_범위_및_주문_전_분석_설계서`로 작성한다. 해당 문서에서는 현재 거래가격 기준 매수 시 horizon별 예상 주가 범위와 주문 전 비용/손익/리스크 분석을 상세화한다.

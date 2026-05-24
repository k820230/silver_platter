# 30. ML Watchlist 및 지수 Chart MVP 구현 상태

작성일: 2026-05-22

## 1. 목적

문서 25의 Wave 6 `ML And Risk Index MVP`를 이어서 구현한다. 사용자 지정 종목 watchlist, horizon별 예측 job, 실제값 연결, 오차 요약, 변동성/위험도 chart 조회를 코드와 API 골격으로 반영한다.

## 2. 구현 위치

`/home/jhkim5/silver_platter/silver_platter_app`

## 3. 구현 내용

### 3.1 Watchlist

추가 파일:

- `src/silver_platter/ml_ops.py`

기능:

- 사용자별 종목 등록
- 종목 비활성화 방식 remove
- active watchlist 조회

### 3.2 ML prediction job

기능:

- 지원 horizon 검증
- 1일/1주/1개월/3개월 예측 job 생성
- 기존 baseline prediction engine과 연결
- job 결과를 stored prediction 모델로 변환

### 3.3 Actual 연결과 오차 계산

기능:

- prediction target 도래 후 actual price 연결
- target 도래 prediction의 actual price 자동 매칭
- `available_to_model_at` 기준 미가용 가격 bar 제외
- absolute error 계산
- percentage error 계산
- 종목별 error summary 계산

### 3.4 변동성/위험도 chart

추가 파일:

- `src/silver_platter/charting.py`

기능:

- 종목별 변동성 지수와 위험도 점수 시계열 구성
- 기간 필터
- API 응답용 dict 변환

### 3.5 API

추가 endpoint:

- `POST /api/watchlist/items`
- `DELETE /api/watchlist/items/{user_id}/{security_id}`
- `GET /api/watchlist/items/{user_id}`
- `POST /api/ml/jobs/run`
  - optional actual bar matching
- `POST /api/indices/chart`

## 4. 테스트

추가 테스트:

- `tests/test_ml_ops.py`
- `tests/test_charting.py`

검증 범위:

- watchlist add/remove/list
- prediction job horizon filtering
- stored prediction 생성
- actual price 연결
- due prediction actual 자동 매칭
- not-due/unavailable price bar 자동 매칭 제외
- ML job API actual bar matching
- ML job API error summary response
- error summary
- 지수 chart filtering/sorting

## 5. 남은 실제 연동

- watchlist 영속 저장
- ML job queue/RQ 연결
- model artifact 저장소 연결
- model performance dashboard
- 지수 시계열 Goldilocks writer

## 6. 검증 명령

실행 위치:

`/home/jhkim5/silver_platter/silver_platter_app`

검증 명령:

- `./scripts/lint`
- `./scripts/test`
- `./scripts/check`

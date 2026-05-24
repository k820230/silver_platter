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
- watchlist registry JSON 저장/복구
- `WATCHLIST_STORE_PATH` 설정 시 watchlist API JSON persistence
- watchlist Goldilocks repository writer SQL generation

### 3.2 ML prediction job

기능:

- 지원 horizon 검증
- 1일/1주/1개월/3개월 예측 job 생성
- 기존 baseline prediction engine과 연결
- job 결과를 stored prediction 모델로 변환
- model registry artifact JSON 저장/복구
- model fine-tuning 적용/미적용 사유 artifact 저장
- model feature set version artifact 저장
- in-memory prediction job queue
- RQ 호환 `queue.enqueue()` 경계 helper

### 3.3 Actual 연결과 오차 계산

기능:

- prediction target 도래 후 actual price 연결
- target 도래 prediction의 actual price 자동 매칭
- `available_to_model_at` 기준 미가용 가격 bar 제외
- absolute error 계산
- percentage error 계산
- 종목별 error summary 계산
- model performance summary Goldilocks repository writer SQL generation

### 3.4 변동성/위험도 chart

추가 파일:

- `src/silver_platter/charting.py`

기능:

- 종목별 변동성 지수와 위험도 점수 시계열 구성
- 기간 필터
- API 응답용 dict 변환
- index chart snapshot Goldilocks repository writer SQL generation

### 3.5 API

추가 endpoint:

- `POST /api/watchlist/items`
- `DELETE /api/watchlist/items/{user_id}/{security_id}`
- `GET /api/watchlist/items/{user_id}`
- `POST /api/ml/jobs/run`
  - optional actual bar matching
- `POST /api/indices/chart`

### 3.6 Web dashboard

기능:

- 현재 ML forecast와 별도 성능 샘플 호출
- model performance 카드에서 sample count, MAE, MAPE 표시
- 기존 `error_summary` API 응답을 dashboard 지표로 연결

## 4. 테스트

추가 테스트:

- `tests/test_ml_ops.py`
- `tests/test_charting.py`

검증 범위:

- watchlist add/remove/list
- watchlist JSON persistence round trip
- watchlist API configured persistence
- watchlist repository writer SQL generation
- prediction job horizon filtering
- in-memory ML job queue FIFO 실행
- RQ enqueue boundary
- model registry artifact round trip
- model fine-tuning reason/feature set artifact round trip
- stored prediction 생성
- actual price 연결
- due prediction actual 자동 매칭
- not-due/unavailable price bar 자동 매칭 제외
- ML job API actual bar matching
- ML job API error summary response
- Web dashboard model performance summary display
- error summary
- model performance summary repository writer SQL generation
- 지수 chart filtering/sorting
- index chart snapshot repository writer SQL generation

## 5. 남은 실제 연동

- 없음

## 6. 검증 명령

실행 위치:

`/home/jhkim5/silver_platter/silver_platter_app`

검증 명령:

- `./scripts/lint`
- `./scripts/test`
- `./scripts/check`

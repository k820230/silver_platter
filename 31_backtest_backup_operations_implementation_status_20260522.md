# 31. 백테스트 및 백업 운영 MVP 구현 상태

작성일: 2026-05-22

## 1. 목적

문서 18과 22의 실거래 전 검증/운영 증적 요구사항을 코드로 착수한다. 이번 작업은 미래데이터 누수 방지, simulation risk gate 재사용, 시나리오 충격 계산, 백업 manifest와 restore check를 구현한다.

## 2. 구현 위치

`/home/jhkim5/silver_platter/silver_platter_app`

## 3. 구현 내용

### 3.1 Backtest/replay

추가 파일:

- `src/silver_platter/backtest.py`

기능:

- backtest run config
- strategy order candidate
- `available_to_model_at` 기반 lookahead violation 검사
- simulation engine 재사용
- 주문별 accepted/reason/realized PnL event 기록
- basic metrics

### 3.2 Scenario shock

기능:

- 가격 충격
- 환율 충격
- 유동성 multiplier 충격
- shock 결과 수치화

### 3.3 Backup manifest와 restore check

추가 파일:

- `src/silver_platter/backup.py`

기능:

- backup file SHA-256 계산
- manifest 생성
- manifest 파일 쓰기
- restore check
- 파일 누락, 크기 불일치, checksum mismatch 검출

### 3.4 Weekly backup scheduler helper

수정 파일:

- `src/silver_platter/worker/scheduler.py`

기능:

- MVP 백업 스케줄: 토요일 10:00
- 현재 시각 이후 다음 백업 예정 시각 계산
- scheduler startup log에 다음 백업 예정 시각 표시

## 4. 테스트

추가 테스트:

- `tests/test_backtest.py`
- `tests/test_backup.py`
- `tests/test_scheduler.py`

검증 범위:

- lookahead violation count
- backtest가 simulation risk gate를 재사용하는지
- scenario shock 계산
- backup manifest 생성
- restore check 성공
- checksum mismatch 실패 검출
- 토요일 10:00 다음 실행 시각 계산

## 5. 남은 실제 연동

- Goldilocks backtest result writer
- strategy plugin interface
- parquet snapshot 기반 대량 replay
- 월간 restore drill scheduler
- 백업 실행 lock과 중복 실행 방지
- 운영 대시보드의 backup/restore 상태 조회

## 6. API 및 Schema

추가 endpoint:

- `POST /api/backtests/run`
- `POST /api/scenarios/shock`
- `POST /api/operations/restore-check`

추가 migration:

- `migrations/008_backtest_restore_operations.sql`

추가 테이블:

- `backtest_run`
- `backtest_order_event`
- `backtest_metric`
- `scenario_result`
- `restore_check_run`

## 7. 검증 명령

실행 위치:

`/home/jhkim5/silver_platter/silver_platter_app`

검증 명령:

- `./scripts/lint`
- `./scripts/test`
- `./scripts/check`

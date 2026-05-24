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
- `src/silver_platter/strategies.py`
- `src/silver_platter/replay.py`
- `scripts/replay_exported_snapshot`

기능:

- backtest run config
- strategy order candidate
- `available_to_model_at` 기반 lookahead violation 검사
- simulation engine 재사용
- 주문별 accepted/reason/realized PnL event 기록
- basic metrics
- paper replay evidence 생성
  - replay day count
  - accepted/blocked order count
  - lookahead violation count
  - broker send attempted 여부
  - required minimum day 기준 pass/fail
- exported snapshot 기반 replay 입력 로딩
- jsonl/parquet snapshot path 또는 directory 기반 replay runner
- strategy plugin registry
- built-in fixed-close strategy plugin
- built-in momentum-threshold strategy plugin
- Web UI strategy plugin selection과 momentum parameter 입력
- backtest run/order event/metric repository writer
- scenario result repository writer

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
- backup execution lock과 중복 실행 방지
- restore check
- restore check repository writer
- backup/restore status summary
- 파일 누락, 크기 불일치, checksum mismatch 검출

### 3.4 Backup/restore scheduler helper

수정 파일:

- `src/silver_platter/worker/scheduler.py`

기능:

- MVP 백업 스케줄: 토요일 10:00
- MVP restore drill 스케줄: 매월 1일 11:00
- 현재 시각 이후 다음 백업 예정 시각 계산
- 현재 시각 이후 다음 restore drill 예정 시각 계산
- 월말 길이가 짧은 달의 restore drill 일자 보정
- scheduler startup log에 다음 백업 예정 시각 표시

## 4. 테스트

추가 테스트:

- `tests/test_backtest.py`
- `tests/test_api.py`
- `tests/test_exports.py`
- `tests/test_replay.py`
- `tests/test_backup.py`
- `tests/test_scheduler.py`

검증 범위:

- lookahead violation count
- backtest가 simulation risk gate를 재사용하는지
- scenario shock 계산
- paper replay evidence pass/fail
- paper replay broker-send attempt 실패 처리
- exported snapshot file 기반 backtest 실행
- exported snapshot path/directory 기반 replay runner
- replay runner CLI JSON output
- strategy plugin registry와 built-in plugin 목록
- momentum-threshold strategy plugin 주문 발생 조건
- unknown strategy plugin 400 response
- exported snapshot replay missing path 400 response
- backtest repository SQL generation
- scenario result repository SQL generation
- restore check repository SQL generation
- backup manifest 생성
- backup manifest/checksum self-file exclusion
- backup manifest final base path recording for staging writes
- backup manifest checksum path-stable hash 기록
- in-progress backup manifest discovery 제외
- backup execution lock 중복 acquire 방지
- backup wrapper lock smoke
- backup wrapper configured command manifest/restore smoke
- backup wrapper skip without fake manifest
- backup wrapper invalid date preflight
- backup wrapper root base directory guard
- backup wrapper command failure lock cleanup
- backup wrapper failed rerun preserves existing dated backup
- backup wrapper successful rerun replaces existing dated backup
- backup wrapper empty successful command rejection
- backup wrapper existing lock exit
- backup/restore status missing/ok/critical 판정
- stale backup degraded 판정
- missing backup date degraded 판정
- invalid backup date degraded 판정
- restore check 성공
- manifest checksum match 성공 검증
- manifest checksum mismatch 실패 검출
- checksum mismatch 실패 검출
- empty backup manifest 실패 검출
- invalid backup manifest JSON 실패 검출
- invalid backup manifest root/files type 실패 검출
- backup manifest base path escape 실패 검출
- backup manifest directory entry 실패 검출
- 토요일 10:00 다음 실행 시각 계산
- 매월 restore drill 다음 실행 시각 계산
- 31일 schedule의 짧은 달 마지막 일자 보정

## 5. 남은 실제 연동

- Goldilocks 실제 ODBC 대상 backtest writer smoke
  - `scripts/goldilocks_repository_smoke` 준비 완료, 기본은 rollback-only smoke opt-in 전 skip
- 장기 대량 replay는 실제 snapshot 확보 후 실행/튜닝 필요

## 6. API 및 Schema

추가 endpoint:

- `POST /api/backtests/run`
- `POST /api/backtests/replay-exported-snapshot`
- `GET /api/backtests/strategy-plugins`
- `POST /api/scenarios/shock`
- `POST /api/operations/restore-check`
- `GET /api/operations/backup-status`

`POST /api/backtests/run` 응답에는 `paper_replay_evidence`가 포함된다.

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

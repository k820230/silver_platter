# 33. 검증 Gate Evidence MVP 구현 상태

작성일: 2026-05-22

## 1. 목적

문서 23의 G2~G8 검증 gate를 코드에서 평가할 수 있도록 gate requirement, evidence, assessment 모델을 추가한다. 실거래 전환 전 필요한 증적을 단순 체크리스트가 아니라 API로 평가 가능한 구조로 전환하는 것이 목적이다.

## 2. 구현 위치

`/home/jhkim5/silver_platter/silver_platter_app`

## 3. 구현 내용

추가 파일:

- `src/silver_platter/verification.py`
- `migrations/009_verification_alert_evidence.sql`

기능:

- gate requirement 모델
- gate evidence 모델
- 기본 G2/G3/G4/G5/G6/G7/G8 requirement catalog
- gate별 evidence 평가
- missing/failed evidence 분리
- paper replay evidence를 G6 gate evidence로 변환
- live safety 결과를 G7 gate evidence로 변환
- gate assessment/evidence Goldilocks repository SQL generation
- API 응답용 dict 변환

## 4. API

추가 endpoint:

- `POST /api/verification/gates/assess`

## 5. 테스트

추가 테스트:

- `tests/test_verification.py`
- `tests/test_repository.py`

검증 범위:

- 모든 증적이 pass이면 gate pass
- 증적 누락 시 gate blocked
- missing requirement 목록 제공
- G6 paper replay evidence pass 평가
- G6 broker send attempt 실패 평가
- G7 live safety evidence pass 평가
- G7 live order enabled default 실패 평가
- verification gate assessment/evidence repository SQL generation

## 6. 남은 실제 연동

- `scripts/check`, `scripts/smoke_api`, 백업 검증 결과 자동 evidence 변환
- G7 제한 실거래 실계좌/모의투자 실측 smoke
- 운영 UI에서 gate 상태 표시

## 7. 검증 명령

실행 위치:

`/home/jhkim5/silver_platter/silver_platter_app`

검증 명령:

- `./scripts/lint`
- `./scripts/test`
- `./scripts/check`

# 28. 데이터 파이프라인 MVP 구현 상태

작성일: 2026-05-22

## 1. 목적

문서 25의 Wave 2 `Data Pipeline MVP`를 실제 코드로 착수한다. 이번 산출물은 외부 API 실연동 전 단계에서 provider contract, 데이터 품질 검사, raw manifest, export 경로를 먼저 고정하는 데 목적이 있다.

## 2. 구현 위치

모든 구현은 `/home/jhkim5/silver_platter/silver_platter_app` 하위에서 관리한다.

## 3. 구현 내용

### 3.1 Provider adapter interface

추가 파일:

- `src/silver_platter/providers.py`

구현 항목:

- 시장 가격 provider interface
- 종목 master/reference provider interface
- 공시 metadata provider interface
- 환율 provider interface
- static provider test double
- MVP provider catalog

MVP catalog에는 다음 source가 포함된다.

- `krx_free`
- `opendart`
- `krx_kind`
- `sec_edgar`
- `free_fx_placeholder`

### 3.2 Ingestion 결과와 raw manifest

추가 파일:

- `src/silver_platter/data_pipeline.py`

구현 항목:

- 가격 bar 수집 결과
- 종목 reference 수집 결과
- 공시 metadata 수집 결과
- 환율 수집 결과
- canonical payload 기반 SHA-256 manifest
- quality status 연결

### 3.3 데이터 품질 연결

기존 `src/silver_platter/data_quality.py`의 `evaluate_price_bars`를 ingestion 결과에 연결했다.

검사 항목:

- 중복 bar
- invalid close
- invalid volume
- turnover 누락
- `available_to_model_at` 누락
- empty dataset

### 3.4 Export helper

추가 파일:

- `src/silver_platter/exports.py`

구현 항목:

- 날짜 partition 기반 가격 bar export
- parquet 우선 요청
- `pyarrow` 미설치 환경에서는 `jsonl` fallback
- export file별 SHA-256 checksum
- DuckDB/분석 pipeline 연결을 위한 partition 구조

### 3.5 API

추가 endpoint:

- `POST /api/data/price-bars/quality`

용도:

- provider 수집 직후 가격 bar 품질 상태를 API로 확인

## 4. 테스트

추가 테스트:

- `tests/test_providers.py`
- `tests/test_data_pipeline.py`
- `tests/test_exports.py`

검증 범위:

- MVP provider catalog
- static reference/disclosure/FX provider filtering
- price bar ingestion quality와 manifest 생성
- raw manifest digest 안정성
- partitioned export 파일 생성과 checksum

## 5. 남은 실제 연동

이번 작업은 adapter contract와 local pipeline foundation이다. 다음 항목은 실제 provider별 API credential, rate limit, 데이터 포맷 확인 후 연결한다.

- KRX/Koscom 무료 데이터 source connector
- OpenDART 수집 connector
- KRX KIND 수집 connector
- SEC EDGAR 수집 connector
- 환율 source connector
- Goldilocks load writer
- parquet dependency 선택과 운영 이미지 반영

## 6. 검증 명령

실행 위치:

`/home/jhkim5/silver_platter/silver_platter_app`

검증 명령:

- `./scripts/lint`
- `./scripts/test`
- `./scripts/check`

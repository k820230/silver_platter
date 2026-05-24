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
- CSV FX rate provider
- MVP provider catalog
- KRX Data Marketplace daily price connector
  - `data.krx.co.kr` OTP/download CSV 호출 경로
  - KRX 일별 종목 시세 table `MDCSTAT01501`
  - 종목코드/종가/거래량/거래대금 normalization
  - 장마감 이후 사용 가능 시각 `16:00` 고정으로 lookahead guard 연동
- `scripts/krx_price_smoke` read-only network smoke, opt-in 기본 skip
- SEC EDGAR submissions metadata connector
  - `data.sec.gov/submissions/CIK##########.json` 호출 경로
  - User-Agent 선언 필수 검증
  - ticker -> CIK lookup 주입
  - form type filtering
  - accession/archive index URL 정규화
  - filing metadata만 저장하고 본문은 저장하지 않음
- `scripts/sec_edgar_smoke` read-only network smoke
- OpenDART disclosure search metadata connector
  - `opendart.fss.or.kr/api/list.json` 호출 경로
  - API key 필수 검증
  - symbol -> corp_code lookup 주입
  - 날짜 범위 filtering
  - DART receipt URL 정규화
- `scripts/opendart_smoke` read-only network smoke
- KRX KIND disclosure search metadata connector
  - `kind.krx.co.kr/disclosure/searchdisclosurebycorp.do` 회사별검색 호출 경로
  - KIND HTML table parser
  - row number/time/company/title/filer normalization
  - title link source URL 보존
- `scripts/krx_kind_smoke` read-only network smoke, opt-in 기본 skip
- 한국은행 ECOS FX rate connector
  - `ecos.bok.or.kr/api/StatisticSearch` 호출 경로
  - 주요국 통화의 대원화환율 기본 통계코드 `731Y001`
  - USD/KRW, JPY/KRW, EUR/KRW 기본 item code mapping
  - ECOS `TIME`, `DATA_VALUE` row normalization
- `scripts/ecos_fx_smoke` read-only network smoke, `ECOS_API_KEY` 미설정 시 기본 skip
- KIS 국내 일봉 주식 정보 API 기반 신규 종목 history prefetch
  - `POST /api/securities/search`와 신규 watchlist 추가 시 Goldilocks `SP.price_bar` 저장 경로 사용
  - `scripts/history_prefetch_smoke` opt-in DB-backed smoke
- `scripts/provider_smoke` guarded provider smoke suite

MVP catalog에는 다음 source가 포함된다.

- `krx_free`
- `krx_data`
- `opendart`
- `krx_kind`
- `sec_edgar`
- `ecos_bok`
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
- data quality score
- latest-window average turnover
- corporate action price/volume adjustment helper

### 3.4 Export helper

추가 파일:

- `src/silver_platter/exports.py`

구현 항목:

- 날짜 partition 기반 가격 bar export
- parquet 우선 요청
- `pyarrow` 미설치 환경에서는 `jsonl` fallback
- export file별 SHA-256 checksum
- DuckDB/분석 pipeline 연결을 위한 partition 구조
- exported snapshot file에서 가격 bar 재로딩

### 3.5 API

추가 endpoint:

- `POST /api/data/price-bars/quality`

용도:

- provider 수집 직후 가격 bar 품질 상태를 API로 확인

### 3.6 Goldilocks repository writer

추가 파일:

- `src/silver_platter/repository.py`

구현 항목:

- `data_provider` idempotent insert
- `security_master` market/symbol 기준 idempotent insert
- `provider_symbol_map` insert
- `raw_data_manifest` insert
- `data_quality_run` insert
- `price_bar` insert
- `audit_log` insert
- `order_state_event` insert
- `order_idempotency_key` insert
- `backtest_run`, `backtest_order_event`, `backtest_metric` insert
- `verification_gate_assessment`, `verification_gate_evidence` insert
- `alert_delivery_run` insert
- 가격 bar ingestion 결과를 manifest, quality, canonical bar로 저장하는 writer method

## 4. 테스트

추가 테스트:

- `tests/test_providers.py`
- `tests/test_data_quality.py`
- `tests/test_data_pipeline.py`
- `tests/test_exports.py`

검증 범위:

- MVP provider catalog
- static reference/disclosure/FX provider filtering
- KRX daily price CSV normalization
- SEC EDGAR submission metadata normalization
- OpenDART disclosure metadata normalization
- KRX KIND disclosure HTML normalization
- ECOS FX rate metadata normalization
- CSV FX rate provider loading and required-column validation
- Goldilocks repository SQL command generation
- audit/order/backtest repository SQL command generation
- verification/alert repository SQL command generation
- price bar ingestion quality와 manifest 생성
- data quality score 산출
- 최신 window 평균 거래대금 계산
- corporate action 이전 bar 가격/거래량 조정
- raw manifest digest 안정성
- partitioned export 파일 생성과 checksum
- exported snapshot round-trip 로딩

## 5. 남은 실제 연동

이번 작업은 adapter contract와 local pipeline foundation이다. 다음 항목은 실제 provider별 API credential, rate limit, 데이터 포맷 확인 후 연결한다.

- KRX Data Marketplace daily price network smoke는 opt-in 실행 시 KRX portal OTP가 `LOGOUT`을 반환해 blocked
- OpenDART network smoke 완료: 실제 API key 환경에서 disclosure_count=100 응답 확인
- KRX KIND network smoke 완료
- SEC EDGAR network smoke 완료: 실제 contact User-Agent 환경에서 AAPL disclosure metadata 응답 확인
- ECOS FX network smoke 완료: 실제 API key 환경에서 USD/KRW rates=10, latest `2026-05-22 1503.5000` 응답 확인
- Goldilocks 실제 ODBC connection 대상 writer smoke 완료
- parquet dependency 선택과 운영 이미지 반영

## 6. 검증 명령

실행 위치:

`/home/jhkim5/silver_platter/silver_platter_app`

검증 명령:

- `./scripts/lint`
- `./scripts/test`
- `./scripts/check`

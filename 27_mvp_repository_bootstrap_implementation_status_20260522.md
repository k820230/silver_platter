# 27. MVP 저장소 부트스트랩 및 구현 상태

작성일: 2026-05-22

## 1. 목적

문서 01~26에서 정의한 퀀트 기반 주식 자동매매 프로그램을 실제 구현으로 전환하기 위한 초기 저장소, 실행 구조, 핵심 도메인 모듈, 검증 스크립트를 구성한다.

구현 위치는 `/home/jhkim5/silver_platter/silver_platter_app`이다. `/home/jhkim5/work/product`에는 Goldilocks 소스와 빌드 산출물이 있으므로 Silver Platter 프로젝트 산출물은 `/home/jhkim5/silver_platter` 하위에서만 관리한다.

## 2. 구현 범위

### 2.1 애플리케이션 골격

- Python 패키지: `silver_platter`
- API: FastAPI 기반 REST 골격
- Worker/Scheduler: Redis/RQ 및 APScheduler 연동을 전제로 한 시작점
- Web: React + Vite + TypeScript 기반 운영 대시보드 골격
- DBMS: Goldilocks 외부 listener 접속 설정
- 실행 환경: Docker Compose, API/Worker/Web Dockerfile

### 2.2 도메인 기능

- 주문 전 리스크 게이트
  - 종목별 투자금액 100,000원 ~ 1,000,000,000원 제한
  - 자동 주문 최대 1,000,000,000원 제한
  - 주문 금액 / ADV20 5% 유동성 hard gate
  - 그룹 주문 금액 / 그룹 ADV20 5% 유동성 hard gate
  - 저유동성 종목 ADV20 10억 원 미만 시 슬리피지 3배
- 주문창 실시간 예측 범위
  - 1일, 1주, 1개월, 3개월 가격 범위
  - 예상 손익 하단/상단
  - 예상 슬리피지
- FIFO 매매 기록
  - 매수 lot 생성
  - 매도 체결과 선입선출 lot 연결
  - 실현손익 계산
- 실시간 테스트 모드
  - 가상 계좌
  - 가상 체결
  - FIFO 실현손익 반영
- 종목별 변동성/위험도 지수
  - EWMA 변동성
  - 0~100 변동성 지수
  - 0~100 위험도 점수
- 사업 그룹 기능
  - 표준 산업분류 + 내부 유사도 tag + 수동 보정 기반 분류
  - 그룹 비중, 손실, 유동성 리스크 평가
  - 기준일 대비 그룹별 변동성 변화율 비교
- 글로벌 헤드라인/급변 이벤트
  - 신뢰 provider 필터링: OpenDART, KRX KIND, SEC EDGAR, LSEG, Bloomberg, FactSet, Dow Jones
  - 그룹별 headline 묶음
  - 국제 정세 event tag와 5분 평균 거래량 100% 이상 증가 조건 기반 클라이언트 alert
- 사용자 지정 종목 ML 분석
  - 종목별 model registry
  - fine-tuning 적용 가능 모델 사양
  - 가격, 거래량, 변동성, 위험도 예측 범위
- 공시 영향 분석
  - 과거 공시 유형별 가격 반응 window 분석
  - 신규 공시 발생 시 예상 주가 범위와 영향 기간 산정
- 해외주식 양도소득세 예상
  - 해당 연도 해외주식 실현손익 기반 단순 보조 리포트
  - 기본공제, 국세, 지방소득세는 설정 가능 값으로 분리
- DB 백업
  - 매주 토요일 오전 10시 실행 정책
  - `/home/jhkim5/backup_sp/YYYY-MM-DD` 날짜별 폴더
  - 무기한 보존

## 3. 생성된 주요 파일

- `README.md`
- `pyproject.toml`
- `docker-compose.yml`
- `docker/api.Dockerfile`
- `docker/worker.Dockerfile`
- `docker/web.Dockerfile`
- `migrations/001_provider_security_market_data.sql`
- `migrations/002_account_fifo.sql`
- `migrations/003_risk_order_backup.sql`
- `migrations/004_seed_policy.sql`
- `migrations/005_simulation_ml_group_index.sql`
- `scripts/test`
- `scripts/lint`
- `scripts/check`
- `scripts/migrate`
- `scripts/seed_verify`
- `scripts/goldilocks_backup.sh`
- `src/silver_platter/risk.py`
- `src/silver_platter/order_preview.py`
- `src/silver_platter/accounting.py`
- `src/silver_platter/simulation.py`
- `src/silver_platter/data_quality.py`
- `src/silver_platter/indices.py`
- `src/silver_platter/business_groups.py`
- `src/silver_platter/headlines.py`
- `src/silver_platter/ml.py`
- `src/silver_platter/disclosures.py`
- `src/silver_platter/tax.py`
- `src/silver_platter/api/main.py`
- `web/src/main.tsx`
- `web/src/styles.css`

## 4. API 골격

- `GET /health`
- `POST /api/orders/preview`
- `POST /api/ml/predictions`
- `POST /api/groups/volatility/compare`
- `POST /api/events/geopolitical-alert`
- `POST /api/disclosures/impact-preview`
- `POST /api/tax/overseas-capital-gains`

## 5. 검증 결과

실행 위치: `/home/jhkim5/silver_platter/silver_platter_app`

- `./scripts/lint`: 통과
- `./scripts/test`: 26개 테스트 통과
- `./scripts/migrate status`: migration 5개 확인
- `./scripts/seed_verify`: MVP seed policy 값 확인
- `docker-compose config`: 통과
- `npm --prefix web install`: 통과
- `npm --prefix web run build`: 통과
- `./scripts/check`: 통합 검증 통과
- `GET http://localhost:8000/health`: 200 응답 확인
- `POST http://localhost:8000/api/orders/preview`: 200 응답 확인

로컬 shell에서 `/health`의 Goldilocks component는 `host.docker.internal` 이름 해석 문제로 `degraded`로 표시되었다. Docker Compose 환경에서는 `extra_hosts`가 설정되어 있으므로 Goldilocks listener가 열려 있을 때 TCP 연결 확인이 가능하다.

## 6. 아직 실제 연동이 필요한 항목

현재 구현은 MVP를 개발 가능한 코드 구조로 전환한 상태이며, 다음 항목은 실서비스 전 실제 연동이 필요하다.

- Goldilocks 실접속 migration 적용 도구
- 한국투자증권 실거래 API adapter
- KRX/Koscom/무료 API/상용 provider별 수집 connector
- OpenDART/KRX KIND/SEC EDGAR 공시 collector
- LSEG/Bloomberg/FactSet/Dow Jones 계약 API collector
- 실시간 tick stream과 Redis Streams/RQ job 연결
- ML 학습 pipeline과 model artifact 저장소
- 실거래 kill switch, 주문 승인 workflow, audit log hardening

## 7. 운영 원칙

- 실거래 주문 전송은 기본 비활성화한다.
- 시뮬레이션 주문은 broker adapter로 전송하지 않는다.
- 해외주식 세금 화면은 신고 보조 추정으로만 표시한다.
- 무료 provider 데이터는 품질 상태와 lookahead 방지 시각을 함께 기록한다.
- 라이선스가 제한된 뉴스 원문은 저장하지 않고 headline과 metadata만 저장한다.

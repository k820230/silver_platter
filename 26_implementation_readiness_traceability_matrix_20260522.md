# 26. 구현 착수 준비 및 요구사항 추적 매트릭스

작성일: 2026-05-22  
기준 문서:

- `01_quant_auto_trading_requirements_definition_20260522.md`
- `23_verification_operations_checklist_20260522.md`
- `24_open_decisions_resolution_register_20260522.md`
- `25_mvp_implementation_backlog_breakdown_20260522.md`

## 1. 목적

이 문서는 문서 단계 종료 후 실제 구현을 시작하기 위한 준비 상태를 점검하고, 요구사항과 backlog, 검증 gate를 연결한다.

## 2. 구현 착수 기준

### 2.1 착수 가능

아래 범위는 현재 결정사항만으로 구현 착수가 가능하다.

| 범위 | 근거 |
| --- | --- |
| 프로젝트 골격과 Docker Compose | Goldilocks external DB, Redis, web/api/worker/scheduler 확정 |
| Goldilocks schema migration | 03/04 문서와 25번 Wave 1 |
| provider adapter interface | 05 문서와 25번 Wave 2 |
| 거래 원장/FIFO | FIFO 모든 계좌 강제 확정 |
| 주문 preview | 금액 한도, 유동성 5%, 슬리피지 3배 확정 |
| risk rule engine | risk result model과 주요 hard gate 확정 |
| simulation 기본 골격 | broker 미전송과 가상 계좌 구조 확정 |
| 백업 policy seed | 토요일 10:00 KST, 경로, 무한 보존 확정 |

### 2.2 실거래 전 검증 Gate

아래 항목은 결정값이 존재하므로 구현은 가능하다. 실거래 자동주문 활성화 전에는 실제 계좌/API/운영 증적을 검증한다.

| 항목 | 차단 범위 |
| --- | --- |
| 종목/섹터/통화/사업그룹 최대 비중 | seed 적용과 risk gate 테스트 |
| 일일 손실과 MDD hard stop | stop 발생 시 자동주문 중단 테스트 |
| 환율 source 우선순위 | preview/세금 계산 fallback 테스트 |
| 한국투자증권 계좌별 상품/시간 | 실제 API orderable 응답 확인 |
| kill switch 정책 | 신규 주문 차단과 수동 일괄 취소 명령 확인 |
| 공시 taxonomy와 MVP source | 공시 영향 예측 신뢰도 |

## 3. 문서 산출물 현황

| 번호 | 문서 | 상태 |
| --- | --- | --- |
| 01 | 요구사항 정의서 | 완료 |
| 02 | 전체 시스템 아키텍처 | 완료 |
| 03 | 도메인 데이터 모델 ERD | 완료 |
| 04 | Goldilocks 초기 스키마 | 완료 |
| 05 | 데이터 수집 파이프라인 | 완료 |
| 06 | 거래 원장/FIFO | 완료 |
| 07 | 해외 주식 세금 | 완료 |
| 08 | 실시간 테스트/가상 계좌 | 완료 |
| 09 | 공시 이벤트 영향 분석 | 완료 |
| 10 | 리스크 엔진 | 완료 |
| 11 | 사업 그룹/그룹 리스크 | 완료 |
| 12 | 글로벌 headline/event risk | 완료 |
| 13 | 국제 정세 알림 | 완료 |
| 14 | 사용자 지정 종목 ML | 완료 |
| 15 | 변동성/위험도 지수 | 완료 |
| 16 | 그룹 변동성 비교 | 완료 |
| 17 | 주문창 실시간 예측 | 완료 |
| 18 | 백테스트/시나리오 | 완료 |
| 19 | Web UI/모바일 화면 | 완료 |
| 20 | Docker Compose 개발 환경 | 완료 |
| 21 | 브로커 API/주문 상태 | 완료 |
| 22 | DB 백업/복구 | 완료 |
| 23 | 검증/운영 체크리스트 | 완료 |
| 24 | 미결정 사항 확정 레지스터 | 완료 |
| 25 | MVP 구현 Backlog | 완료 |
| 26 | 구현 착수 준비/추적 매트릭스 | 완료 |

## 4. 요구사항-Backlog 추적

| 요구사항 영역 | 대표 요구사항 | Backlog | 검증 |
| --- | --- | --- | --- |
| DBMS/환경 | Goldilocks, Compose | E-01, E-02 | G2 개발 환경 |
| 데이터 수집 | provider adapter, quality | E-03 | G3 데이터 검증 |
| 거래 원장 | FIFO, realized PnL | E-04 | 회계/FIFO 체크 |
| 세금 | 해외 주식 보조 리포트 | E-04, E-06 | 세금 체크 |
| 리스크 한도 | 금액, 유동성, 손실, 그룹 | E-05 | 리스크 체크 |
| 주문창 | preview, 가격범위, 비용 | E-06 | 주문/체결 체크 |
| 브로커 | 한국투자증권, state machine | E-06 | 주문/체결 체크 |
| ML 분석 | horizon, fine-tuning | E-07 | ML/예측 체크 |
| 변동성/위험도 | 0~100 지수 | E-07 | 리스크/UI 체크 |
| 사업 그룹 | 분류, 그룹 리스크 | E-08 | 리스크/UI 체크 |
| 헤드라인/이벤트 | metadata, 급변 알림 | E-08 | 알림/UI 체크 |
| Web UI | 대시보드, 주문, 운영 | E-09 | UI 체크 |
| simulation/backtest | 가상 계좌, replay | E-10 | 백테스트/시뮬레이션 체크 |
| 백업/복구 | 주간 백업, manifest | E-11 | 백업/복구 체크 |
| 감사 | 주문/알림/설정 audit | E-11 | 보안/감사 체크 |

## 5. 첫 구현 Milestone

### Milestone M1. Local Skeleton

목표: 빈 서비스라도 local에서 기동하고 health를 확인한다.

완료 기준:

- `docker compose --profile dev up` 가능
- API `/health` 응답
- Redis ping
- Goldilocks connection config 로딩
- worker heartbeat log

### Milestone M2. Schema And Seed

목표: Goldilocks에 핵심 schema와 기본 seed를 적용한다.

완료 기준:

- migration runner 실행
- provider/risk/backup seed 적용
- 유동성 5%, 슬리피지 3배, 금액 한도 seed 확인
- migration 재실행 idempotent

### Milestone M3. Order Preview Risk Gate

목표: 실거래 없이 주문 preview와 risk gate를 검증한다.

완료 기준:

- 주문금액 한도 block
- 유동성 5% 초과 block
- 저유동성 3배 슬리피지 warning
- 매도 FIFO preview
- simulation mode broker 미전송

### Milestone M4. Simulation Evidence

목표: 가상 계좌와 replay로 G4 gate 증적을 만든다.

완료 기준:

- virtual account 생성/초기화
- simulated execution 생성
- transaction ledger/FIFO/PnL 반영
- risk_check_result 저장
- UI 또는 report로 결과 확인

## 6. 착수 전 파일/명령 체크

구현 시작 직후 확인할 명령 후보:

```bash
git status --short
docker compose --profile dev config
docker compose --profile dev up
```

schema 작성 후 확인할 명령 후보:

```bash
./scripts/migrate up
./scripts/migrate status
./scripts/seed verify
```

테스트 작성 후 확인할 명령 후보:

```bash
./scripts/test
./scripts/lint
```

실제 명령은 구현 언어와 패키지 관리자를 확정한 뒤 repo에 맞게 조정한다.

## 7. 구현 전 위험과 대응

| 위험 | 영향 | 대응 |
| --- | --- | --- |
| Goldilocks driver/CLI 정보 부족 | migration 지연 | 먼저 local connection spike 수행 |
| 한국투자증권 API 계좌 검증 지연 | live adapter 지연 | paper/simulation 우선 구현 |
| 환율 source 장애 | 해외 세금 표시 지연 | 결정된 source 우선순위와 pending_fx 상태 |
| 리스크 한도 과도/과소 설정 | live auto order 위험 증가 | versioned config와 paper/simulation 검증 |
| 공시 taxonomy 오분류 | 공시 예측 품질 저하 | taxonomy V1과 unknown type fallback |
| 외부 모바일 제외 | 모바일 공개 사용 불가 | 내부망 Web/PWA 우선 |

## 8. 구현 착수 판정

현재 상태 기준 판정:

| 항목 | 판정 |
| --- | --- |
| 문서 산출물 | 착수 가능 |
| 결정사항 레지스터 | 착수 가능 |
| MVP backlog | 착수 가능 |
| 개발 환경 설계 | 착수 가능 |
| schema 설계 | 착수 가능 |
| live auto order | paper/simulation 검증 후 제한 활성화 가능 |
| 공개 모바일 접속 | MVP 제외, 내부망 Web/PWA만 허용 |

결론: `Wave 0 Repository Bootstrap`과 `Wave 1 Goldilocks Schema Foundation`부터 구현 착수가 가능하다. live auto order는 결정값이 존재하므로 구현은 가능하지만, paper/simulation 검증과 한국투자증권 실제 orderable 확인 후 제한 활성화한다.

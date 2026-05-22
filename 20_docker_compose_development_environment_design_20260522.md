# 20. Docker Compose 개발 환경 설계

작성일: 2026-05-22  
기준 문서:

- `01_quant_auto_trading_requirements_definition_20260522.md`
- `02_overall_system_architecture_design_20260522.md`
- `04_goldilocks_initial_schema_design_20260522.md`
- `05_data_collection_pipeline_detail_design_20260522.md`
- `22_db_backup_restore_policy_operations_procedure_20260522.md`

## 1. 목적

이 문서는 개발용 및 장기 운영용 PC 서버에서 퀀트 자동매매 프로그램을 실행하기 위한 Docker Compose 기반 개발 환경을 정의한다.

DBMS는 PostgreSQL을 사용하지 않고 현재 환경의 Goldilocks를 기준 DB로 사용한다.

## 2. 적용 범위

### 2.1 포함 범위

- API 서버
- worker/scheduler
- Web UI dev server
- Redis
- DuckDB/Parquet 작업 경로
- Goldilocks 접속 설정
- 백업 작업
- 로그와 volume 구성
- `.env` 설정
- 개발/장기 운영 profile

### 2.2 제외 범위

- Goldilocks 자체 설치 자동화
- Kubernetes 배포
- 공개 인터넷 배포
- 외부 모바일 접속 구성

Goldilocks가 현재 디렉토리 또는 로컬 PC에 이미 준비되어 있다는 전제로 연결 설정을 구성한다.

## 3. 구성 원칙

1. Goldilocks는 기준 DB다.  
   Compose 파일에 PostgreSQL 서비스를 추가하지 않는다.

2. 비밀값은 `.env`와 로컬 secret 파일로 분리한다.  
   API key는 git에 포함하지 않는다.

3. 장기 운영과 개발 profile을 나눈다.  
   개발 profile은 hot reload를 허용하고, 운영 profile은 restart policy와 백업을 우선한다.

4. 데이터와 백업 경로를 명확히 분리한다.  
   백업은 `/home/jhkim5/backup_sp/{backup_date}/`에 생성한다.

## 4. 서비스 구성

| 서비스 | 역할 |
| --- | --- |
| `web` | Web UI |
| `api` | REST/WebSocket API |
| `worker` | 데이터 수집, 모델 작업, 리스크 계산 |
| `scheduler` | 주기 작업, 백업 trigger |
| `redis` | stream/cache |
| `backup-runner` | Goldilocks 백업 절차 실행 |
| `monitor` | 개발용 health summary |

Goldilocks는 외부 local service로 연결한다.

## 5. 네트워크

```text
browser
  -> web
  -> api
  -> redis
  -> local Goldilocks listener
```

Compose network:

- `sp_app_net`: API, worker, web, redis 내부 통신
- Goldilocks는 host network 또는 host alias로 접근

Goldilocks 접속 방식은 로컬 설치 상태에 맞춰 아래 중 하나를 사용한다.

| 방식 | 설명 |
| --- | --- |
| `host.docker.internal` | Docker Desktop 또는 alias 지원 환경 |
| host network | Linux host network profile |
| bridge + host gateway | `extra_hosts`로 host gateway 지정 |

## 6. 환경 변수

`.env` 필수 항목:

```text
APP_ENV=development
APP_TIMEZONE=Asia/Seoul

GOLDILOCKS_HOST=host.docker.internal
GOLDILOCKS_PORT=22581
GOLDILOCKS_DATABASE=GOLDILOCKS
GOLDILOCKS_USER=
GOLDILOCKS_PASSWORD=

REDIS_URL=redis://redis:6379/0

BACKUP_BASE_DIR=/home/jhkim5/backup_sp
PARQUET_EXPORT_DIR=/home/jhkim5/silver_platter_data/parquet
LOG_DIR=/home/jhkim5/silver_platter_logs

KIS_APP_KEY=
KIS_APP_SECRET=
KIS_ACCOUNT_NO=
KIS_API_BASE_URL=
```

한국투자증권 Open API key는 로컬 `.env` 또는 secret manager에만 둔다.

## 7. Volume 구성

| volume/path | 목적 |
| --- | --- |
| `/home/jhkim5/silver_platter_data/parquet` | Parquet export |
| `/home/jhkim5/silver_platter_logs` | 애플리케이션 로그 |
| `/home/jhkim5/backup_sp` | DB 백업 |
| project source bind mount | 개발 hot reload |

## 8. Compose 초안

```yaml
services:
  web:
    build:
      context: .
      dockerfile: docker/web.Dockerfile
    env_file: .env
    ports:
      - "3000:3000"
    depends_on:
      - api
    profiles: ["dev", "ops"]

  api:
    build:
      context: .
      dockerfile: docker/api.Dockerfile
    env_file: .env
    ports:
      - "8000:8000"
    extra_hosts:
      - "host.docker.internal:host-gateway"
    depends_on:
      - redis
    profiles: ["dev", "ops"]

  worker:
    build:
      context: .
      dockerfile: docker/worker.Dockerfile
    env_file: .env
    extra_hosts:
      - "host.docker.internal:host-gateway"
    depends_on:
      - redis
    profiles: ["dev", "ops"]

  scheduler:
    build:
      context: .
      dockerfile: docker/worker.Dockerfile
    command: ["python", "-m", "silver_platter.scheduler"]
    env_file: .env
    extra_hosts:
      - "host.docker.internal:host-gateway"
    depends_on:
      - redis
    volumes:
      - /home/jhkim5/backup_sp:/home/jhkim5/backup_sp
    profiles: ["ops"]

  redis:
    image: redis:7
    ports:
      - "6379:6379"
    profiles: ["dev", "ops"]
```

PostgreSQL 서비스는 포함하지 않는다.

## 9. 개발 profile

개발 profile 특징:

- hot reload
- local `.env`
- 샘플 데이터 seed
- 실거래 주문 기본 비활성
- simulation mode 기본 노출
- 로그 verbose

실행 예:

```bash
docker compose --profile dev up
```

## 10. 장기 운영 profile

장기 운영 profile 특징:

- restart policy 적용
- scheduler 활성화
- 백업 job 활성화
- API key 존재 검사
- healthcheck 강화
- 실거래 활성 여부 명시 설정

운영 profile에서도 자동 주문은 risk gate와 kill switch가 활성화된 경우에만 허용한다.

## 11. Healthcheck

| 서비스 | healthcheck |
| --- | --- |
| web | HTTP `/health` |
| api | HTTP `/health`, Goldilocks ping |
| worker | Redis heartbeat |
| scheduler | 최근 job heartbeat |
| redis | `redis-cli ping` |
| Goldilocks | API가 driver ping으로 확인 |

Goldilocks 연결 실패는 API health degraded로 표시하고 주문 전송을 차단한다.

## 12. Scheduler 작업

주기 작업:

| 작업 | 주기 |
| --- | --- |
| 가격 데이터 수집 | 시장별 schedule |
| 공시 수집 | 1~5분 또는 provider 제한 기준 |
| headline 수집 | 계약/provider 정책 기준 |
| 리스크 지수 계산 | 장 종료 후와 이벤트 발생 시 |
| ML 예측 | 장 종료 후와 장 시작 전 |
| DB 백업 | 매주 토요일 10:00 KST |
| 복구 검증 | 월 1회 또는 수동 |

## 13. 백업 연동

백업 정책:

- 매주 토요일 10:00 KST
- `/home/jhkim5/backup_sp/{backup_date}/`
- 보존 기간 무한
- 암호화 없음
- manifest, checksum, 실행 로그 기록

backup-runner는 Goldilocks 백업 명령을 실행하고 결과를 `db_backup_run`과 로그 파일에 기록한다.

## 14. 보안

금지:

- API key git 저장
- 백업 경로 world-writable
- 실거래 key를 development sample에 포함
- 외부 포트 무분별 공개

권장:

- `.env.example`에는 placeholder만 제공
- 파일 권한 `600` 또는 운영 사용자 전용
- Docker socket mount 금지
- 운영 profile에서는 live order 별도 enable flag 필요

## 15. 로그

로그 분류:

- API request
- broker request/response metadata
- 주문 상태 이벤트
- 데이터 수집 job
- 모델 작업
- 리스크 체크
- 백업 실행
- audit log

민감정보는 마스킹한다.

## 16. 테스트 요구사항

| 테스트 | 검증 |
| --- | --- |
| compose dev 기동 | web/api/worker/redis 정상 |
| Goldilocks ping | PostgreSQL 없이 연결 |
| `.env` 누락 | 명확한 오류 |
| live key 없음 | 실거래 비활성 |
| 백업 volume | `/home/jhkim5/backup_sp` 쓰기 가능 |
| scheduler | 토요일 10:00 KST schedule 등록 |
| restart | worker 재시작 후 job 재개 |

## 17. 구현 기본 결정 사항

1. Goldilocks listener 기본값은 `host.docker.internal:22581`이다.
2. backup 명령은 `scripts/goldilocks_backup.sh` wrapper가 Goldilocks native online backup을 호출한다.
3. API는 FastAPI, worker는 Python, Web은 React + Vite + TypeScript로 시작한다.
4. application log 보존 기간은 180일, audit log는 DB에 영구 보존한다.
5. 장기 운영 supervisor는 Docker Compose를 기본으로 하고, host 부팅 자동화는 systemd unit으로 Compose를 감싼다.

## 18. 다음 산출물

다음 문서는 `21_브로커_API_연동_및_주문_상태_기계_설계`로 작성한다. 해당 문서에서는 한국투자증권 Open API adapter, 주문 상태 전이, idempotency, kill switch, 주문 이벤트 대사를 상세화한다.

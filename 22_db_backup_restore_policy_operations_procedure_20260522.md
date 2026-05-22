# 22. DB 백업/복구 정책 및 운영 절차 설계서

작성일: 2026-05-22  
기준 문서:

- `01_quant_auto_trading_requirements_definition_20260522.md`
- `02_overall_system_architecture_design_20260522.md`
- `03_domain_data_model_erd_draft_20260522.md`
- `04_goldilocks_initial_schema_design_20260522.md`
- `20_docker_compose_development_environment_design_20260522.md`

## 1. 목적

이 문서는 Goldilocks 기준 DB의 정기 백업, 백업 manifest, 복구 절차, 복구 검증, 운영 알림 정책을 정의한다.

## 2. 확정 정책

| 항목 | 정책 |
| --- | --- |
| DBMS | Goldilocks |
| 정기 백업 | 매주 토요일 10:00 KST |
| 저장 위치 | `/home/jhkim5/backup_sp/{backup_date}/` |
| 보존 기간 | 무한 |
| 암호화 | 적용하지 않음 |
| 백업 폴더 | 백업 날짜별 생성 |
| 모니터링 | 성공/실패/크기/checksum/소요시간 기록 |

## 3. 적용 범위

### 3.1 포함 범위

- Goldilocks schema/data backup
- 백업 실행 이력
- 백업 파일 manifest
- checksum
- 복구 절차
- 복구 검증
- 실패 알림
- 운영 대시보드 표시

### 3.2 제외 범위

- PostgreSQL 백업
- 백업 암호화
- 클라우드 원격 백업
- 장기 보존 삭제 정책

## 4. 백업 디렉토리 구조

```text
/home/jhkim5/backup_sp/
  2026-05-23/
    goldilocks/
      schema/
      data/
      logs/
    manifest.json
    checksum.sha256
    backup.log
    restore_check.log
```

날짜는 백업 시작일의 KST 기준 `YYYY-MM-DD`를 사용한다.

## 5. 백업 대상

필수 대상:

- schema metadata
- master data
- price/event/model/risk/order/accounting tables
- audit log
- backup metadata
- migration 기록

보조 대상:

- configuration snapshot
- active model version metadata
- scheduler state
- data quality checkpoint

대용량 Parquet export와 모델 artifact는 DB 백업과 분리해 별도 보존 정책을 둔다.

## 6. 백업 실행 흐름

```text
scheduler trigger 토요일 10:00 KST
  -> backup lock 획득
  -> Goldilocks 연결 확인
  -> 백업 대상/경로 생성
  -> 백업 명령 실행
  -> 파일 목록 수집
  -> checksum 생성
  -> manifest 작성
  -> db_backup_run 기록
  -> 성공/실패 알림
```

동일 scheduled_at 백업이 이미 성공했으면 중복 실행하지 않는다.

## 7. 백업 manifest

`manifest.json` 필수 항목:

```json
{
  "backup_date": "2026-05-23",
  "started_at": "2026-05-23T10:00:00+09:00",
  "completed_at": "2026-05-23T10:12:30+09:00",
  "dbms": "goldilocks",
  "database": "GOLDILOCKS",
  "backup_policy": "weekly_sat_1000_kst",
  "retention": "infinite",
  "encryption": "none",
  "base_path": "/home/jhkim5/backup_sp/2026-05-23",
  "files": [],
  "checksum_file": "checksum.sha256",
  "status": "success"
}
```

## 8. DB 테이블

### 8.1 `db_backup_policy`

| 필드 | 설명 |
| --- | --- |
| `backup_policy_id` | 정책 ID |
| `policy_code` | weekly_sat_1000_kst |
| `schedule_cron` | KST 기준 cron |
| `base_path` | `/home/jhkim5/backup_sp` |
| `retention_days` | null 또는 infinite |
| `encryption_type` | none |
| `is_active` | 활성 여부 |

### 8.2 `db_backup_run`

| 필드 | 설명 |
| --- | --- |
| `backup_run_id` | 실행 ID |
| `backup_policy_id` | 정책 |
| `scheduled_at` | 예정 시각 |
| `started_at` | 시작 |
| `completed_at` | 종료 |
| `status` | running, success, failed |
| `backup_path` | 백업 경로 |
| `total_bytes` | 파일 크기 |
| `checksum_status` | ok, failed |
| `error_message` | 실패 사유 |

### 8.3 `db_backup_manifest`

| 필드 | 설명 |
| --- | --- |
| `backup_manifest_id` | manifest ID |
| `backup_run_id` | 실행 |
| `file_path` | 파일 경로 |
| `file_size` | 크기 |
| `sha256` | checksum |
| `created_at` | 생성 시각 |

## 9. 스케줄

cron 표현:

```text
0 10 * * 6
```

주의:

- timezone은 `Asia/Seoul`로 고정한다.
- scheduler는 KST 기준으로 해석해야 한다.
- PC가 꺼져 있던 경우 다음 기동 시 missed backup을 감지하고 운영자 확인 후 실행한다.

## 10. 실패 처리

| 실패 | 처리 |
| --- | --- |
| Goldilocks 연결 실패 | retry, 운영 알림 |
| 디스크 공간 부족 | 실패 기록, 긴급 알림 |
| 권한 오류 | 실패 기록, 권한 점검 |
| checksum 실패 | 백업 실패 처리 |
| manifest 작성 실패 | 백업 불완전 처리 |
| 중복 실행 | 기존 run 확인 후 skip |

백업 실패는 운영 대시보드와 알림 대상이다.

## 11. 복구 절차

복구는 운영자가 수동으로 시작한다.

```text
복구 대상 backup_date 선택
  -> manifest 확인
  -> checksum 검증
  -> 복구용 Goldilocks instance 준비
  -> schema 복구
  -> data 복구
  -> migration version 확인
  -> row count/checksum 검증
  -> application read-only 검증
  -> 복구 결과 기록
```

운영 DB에 직접 덮어쓰는 복구는 별도 승인 없이 수행하지 않는다.

## 12. 복구 검증

복구 검증 항목:

- manifest 존재
- checksum 일치
- 핵심 테이블 row count
- 최근 주문/체결/원장 조회
- 최근 risk index 조회
- 최근 backup metadata 조회
- application read-only healthcheck

월 1회 복구 검증을 권장한다. 정기 검증 스케줄 최종값은 운영 결정 항목이다.

## 13. 운영 대시보드 표시

표시 항목:

- 마지막 백업 시각
- 마지막 백업 상태
- 백업 파일 크기
- 백업 소요 시간
- checksum 상태
- 최근 실패 횟수
- 마지막 복구 검증일
- 백업 경로

## 14. 보안

현재 정책상 암호화는 적용하지 않는다.

최소 통제:

- 백업 디렉토리 접근 권한 제한
- API key와 secret 파일이 백업에 포함되는지 점검
- 백업 파일 외부 공유 금지
- 감사 로그 보존

## 15. 디스크 관리

보존 기간은 무한이므로 디스크 사용량 모니터링이 필수다.

알림 조건:

- 백업 경로 사용률 80% 이상
- 백업 파일 크기 급감/급증
- 2회 연속 백업 실패
- 월간 복구 검증 실패

## 16. 테스트 요구사항

| 테스트 | 검증 |
| --- | --- |
| schedule | 토요일 10:00 KST trigger |
| 경로 생성 | 날짜별 폴더 |
| manifest | 필수 필드 |
| checksum | 파일 검증 |
| 실패 처리 | 알림과 run 기록 |
| 중복 방지 | same scheduled_at unique |
| 복구 검증 | row count와 healthcheck |
| 암호화 없음 | manifest에 none 기록 |

## 17. 구현 기본 결정 사항

1. Goldilocks 백업은 `scripts/goldilocks_backup.sh` wrapper가 native online backup을 우선 호출한다.
2. 복구 검증 주기는 월 1회다.
3. 백업은 online backup을 우선하고, 미지원 시 maintenance lock 후 logical export를 수행한다.
4. 백업 파일 크기는 최근 4회 median 대비 50% 이상 증감하면 warning으로 처리한다.
5. 원격/외장 저장소는 MVP에서 제외하고 로컬 `/home/jhkim5/backup_sp`만 사용한다.

## 18. 다음 산출물

다음 문서는 `23_검증_운영_체크리스트`로 작성한다. 해당 문서에서는 요구사항, 개발, 데이터, 주문, 리스크, 보안, 백업, 운영 전환에 대한 최종 점검표를 정의한다.

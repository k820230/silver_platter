#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

BACKUP_BASE_DIR="${BACKUP_BASE_DIR:-/home/jhkim5/backup_sp}"
BACKUP_DATE="${BACKUP_DATE:-$(date +%F)}"
TARGET_DIR="${BACKUP_BASE_DIR}/${BACKUP_DATE}"
WORK_DIR="${BACKUP_BASE_DIR}/.${BACKUP_DATE}.in_progress.$$"
LOCK_DIR="${BACKUP_BASE_DIR}/.goldilocks_backup.lock"
POLICY_CODE="${GOLDILOCKS_BACKUP_POLICY:-weekly_goldilocks_full_backup}"
BACKUP_COMMAND="${GOLDILOCKS_BACKUP_COMMAND:-}"

if [ "${BACKUP_BASE_DIR}" = "/" ]; then
  echo "Goldilocks backup aborted: BACKUP_BASE_DIR must not be /" >&2
  exit 64
fi

BACKUP_DATE="${BACKUP_DATE}" python3 - <<'PY'
import os
from datetime import date

try:
    date.fromisoformat(os.environ["BACKUP_DATE"])
except ValueError as exc:
    raise SystemExit("BACKUP_DATE must be an ISO date: %s" % exc)
PY

mkdir -p "${BACKUP_BASE_DIR}"
if ! mkdir "${LOCK_DIR}" 2>/dev/null; then
  echo "Goldilocks backup skipped: another backup appears to be running (${LOCK_DIR})" >&2
  exit 75
fi
trap 'rm -rf "${WORK_DIR}"; rmdir "${LOCK_DIR}" 2>/dev/null || true' EXIT

if [ -z "${BACKUP_COMMAND}" ]; then
  echo "Goldilocks backup skipped: set GOLDILOCKS_BACKUP_COMMAND to run native backup/export" >&2
  exit 0
fi

rm -rf "${WORK_DIR}"
mkdir -p "${WORK_DIR}"

(
  cd "${WORK_DIR}"
  bash -euo pipefail -c "${BACKUP_COMMAND}"
)

BACKUP_TARGET_DIR="${WORK_DIR}" BACKUP_FINAL_DIR="${TARGET_DIR}" BACKUP_DATE="${BACKUP_DATE}" POLICY_CODE="${POLICY_CODE}" PYTHONPATH=src python3 - <<'PY'
import os
from datetime import date
from pathlib import Path

from silver_platter.backup import build_backup_manifest, write_backup_manifest

target = Path(os.environ["BACKUP_TARGET_DIR"])
final_target = Path(os.environ["BACKUP_FINAL_DIR"])
manifest = build_backup_manifest(
    target,
    date.fromisoformat(os.environ["BACKUP_DATE"]),
    policy_code=os.environ["POLICY_CODE"],
    status="success",
    manifest_base_path=final_target,
)
if not manifest.files:
    raise SystemExit("backup command produced no files")
write_backup_manifest(manifest, target / "manifest.json")
PY

sha256sum "${WORK_DIR}/manifest.json" | awk '{print $1}' > "${WORK_DIR}/manifest.sha256"
rm -rf "${TARGET_DIR}"
mv "${WORK_DIR}" "${TARGET_DIR}"
echo "Goldilocks backup completed: ${TARGET_DIR}"

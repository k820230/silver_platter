#!/usr/bin/env bash
set -euo pipefail

BACKUP_BASE_DIR="${BACKUP_BASE_DIR:-/home/jhkim5/backup_sp}"
BACKUP_DATE="$(date +%F)"
TARGET_DIR="${BACKUP_BASE_DIR}/${BACKUP_DATE}"
LOCK_DIR="${BACKUP_BASE_DIR}/.goldilocks_backup.lock"

mkdir -p "${BACKUP_BASE_DIR}"
if ! mkdir "${LOCK_DIR}" 2>/dev/null; then
  echo "Goldilocks backup skipped: another backup appears to be running (${LOCK_DIR})" >&2
  exit 75
fi
trap 'rmdir "${LOCK_DIR}"' EXIT
mkdir -p "${TARGET_DIR}/goldilocks/logs"

cat > "${TARGET_DIR}/manifest.json" <<MANIFEST
{
  "backup_date": "${BACKUP_DATE}",
  "dbms": "goldilocks",
  "backup_policy": "weekly_goldilocks_full_backup",
  "retention": "infinite",
  "encryption": "none",
  "base_path": "${TARGET_DIR}",
  "status": "placeholder"
}
MANIFEST

sha256sum "${TARGET_DIR}/manifest.json" > "${TARGET_DIR}/checksum.sha256"
echo "Goldilocks backup wrapper placeholder wrote ${TARGET_DIR}"

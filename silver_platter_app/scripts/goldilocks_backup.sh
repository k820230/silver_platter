#!/usr/bin/env bash
set -euo pipefail

BACKUP_BASE_DIR="${BACKUP_BASE_DIR:-/home/jhkim5/backup_sp}"
BACKUP_DATE="$(date +%F)"
TARGET_DIR="${BACKUP_BASE_DIR}/${BACKUP_DATE}"

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

import json
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from silver_platter.backup import (
    BackupExecutionLock,
    build_backup_manifest,
    restore_check,
    summarize_backup_restore_status,
    write_backup_manifest,
)


class BackupTests(TestCase):
    def test_backup_manifest_and_restore_check_ok(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            data_file = base / "goldilocks" / "data" / "part.dat"
            data_file.parent.mkdir(parents=True)
            data_file.write_text("payload", encoding="utf-8")
            manifest = build_backup_manifest(base, date(2026, 5, 23))
            manifest_path = base / "manifest.json"
            write_backup_manifest(manifest, manifest_path)

            result = restore_check(manifest_path)

            self.assertEqual("ok", result.status)
            self.assertEqual(1, len(manifest.files))

    def test_restore_check_detects_checksum_mismatch(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            data_file = base / "goldilocks" / "data" / "part.dat"
            data_file.parent.mkdir(parents=True)
            data_file.write_text("payload", encoding="utf-8")
            manifest = build_backup_manifest(base, date(2026, 5, 23))
            manifest_path = base / "manifest.json"
            write_backup_manifest(manifest, manifest_path)
            data_file.write_text("changed", encoding="utf-8")

            result = restore_check(manifest_path)

            self.assertEqual("failed", result.status)
            self.assertIn("checksum mismatch", result.issues[0])

    def test_backup_execution_lock_prevents_duplicate_acquire(self):
        with TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "backup.lock"
            first = BackupExecutionLock(
                lock_path,
                owner_id="worker-1",
                acquired_at=datetime(2026, 5, 23, 10, 0, 0),
            )
            second = BackupExecutionLock(lock_path, owner_id="worker-2")

            self.assertTrue(first.acquire())
            self.assertFalse(second.acquire())
            payload = json.loads(lock_path.read_text(encoding="utf-8"))
            self.assertEqual("worker-1", payload["owner_id"])

            first.release()
            self.assertTrue(second.acquire())
            second.release()

    def test_backup_execution_lock_context_releases_lock(self):
        with TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "backup.lock"

            with BackupExecutionLock(lock_path, owner_id="worker-1") as lock:
                self.assertTrue(lock.acquired)
                self.assertTrue(lock_path.exists())

            self.assertFalse(lock_path.exists())

    def test_backup_restore_status_degraded_when_manifest_missing(self):
        with TemporaryDirectory() as tmp:
            status = summarize_backup_restore_status(
                Path(tmp),
                checked_at=datetime(2026, 5, 23, 10, 0, 0),
            )

        self.assertEqual("degraded", status.status)
        self.assertEqual("missing", status.backup_status)
        self.assertEqual("not_checked", status.restore_status)

    def test_backup_restore_status_ok_for_successful_restorable_manifest(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            data_file = base / "goldilocks" / "data" / "part.dat"
            data_file.parent.mkdir(parents=True)
            data_file.write_text("payload", encoding="utf-8")
            manifest = build_backup_manifest(
                base,
                date(2026, 5, 23),
                status="success",
            )
            manifest_path = base / "manifest.json"
            write_backup_manifest(manifest, manifest_path)

            status = summarize_backup_restore_status(base)

        self.assertEqual("ok", status.status)
        self.assertEqual("success", status.backup_status)
        self.assertEqual("ok", status.restore_status)
        self.assertEqual(str(manifest_path), status.latest_manifest_path)

    def test_backup_restore_status_critical_for_restore_failure(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            data_file = base / "goldilocks" / "data" / "part.dat"
            data_file.parent.mkdir(parents=True)
            data_file.write_text("payload", encoding="utf-8")
            manifest = build_backup_manifest(
                base,
                date(2026, 5, 23),
                status="success",
            )
            manifest_path = base / "manifest.json"
            write_backup_manifest(manifest, manifest_path)
            data_file.unlink()

            status = summarize_backup_restore_status(base)

        self.assertEqual("critical", status.status)
        self.assertEqual("failed", status.restore_status)
        self.assertIn("missing backup file", status.issues[0])

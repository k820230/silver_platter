from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from silver_platter.backup import build_backup_manifest, restore_check, write_backup_manifest


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

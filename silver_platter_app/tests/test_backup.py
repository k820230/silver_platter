import json
import os
from datetime import date, datetime
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
from typing import Optional
from unittest import TestCase

from silver_platter.backup import (
    BackupExecutionLock,
    build_backup_manifest,
    find_latest_backup_manifest,
    restore_check,
    sha256_file,
    summarize_backup_restore_status,
    write_backup_manifest,
)


class BackupTests(TestCase):
    def _backup_script(self) -> Path:
        return Path(__file__).resolve().parents[1] / "scripts" / "goldilocks_backup.sh"

    def _backup_script_env(
        self,
        backup_base_dir: str,
        backup_date: str = "2026-05-23",
        backup_command: Optional[str] = None,
    ) -> dict:
        env = {
            **os.environ,
            "BACKUP_BASE_DIR": backup_base_dir,
            "BACKUP_DATE": backup_date,
        }
        if backup_command is None:
            env.pop("GOLDILOCKS_BACKUP_COMMAND", None)
        else:
            env["GOLDILOCKS_BACKUP_COMMAND"] = backup_command
        return env

    def _run_backup_script(
        self,
        backup_base_dir: str,
        backup_date: str = "2026-05-23",
        backup_command: Optional[str] = None,
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(self._backup_script())],
            env=self._backup_script_env(backup_base_dir, backup_date, backup_command),
            check=False,
            capture_output=True,
            text=True,
        )

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

    def test_backup_manifest_excludes_manifest_and_checksum_files(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            data_file = base / "goldilocks" / "data" / "part.dat"
            data_file.parent.mkdir(parents=True)
            data_file.write_text("payload", encoding="utf-8")
            (base / "manifest.json").write_text("{}", encoding="utf-8")
            (base / "manifest.sha256").write_text("sha manifest.json", encoding="utf-8")
            (base / "checksum.sha256").write_text("legacy checksum", encoding="utf-8")

            manifest = build_backup_manifest(base, date(2026, 5, 23))

        self.assertEqual(
            ["goldilocks/data/part.dat"],
            [entry.relative_path for entry in manifest.files],
        )

    def test_backup_manifest_can_record_final_base_path_for_staging_dir(self):
        with TemporaryDirectory() as tmp:
            work_dir = Path(tmp) / ".2026-05-23.in_progress.1"
            final_dir = Path(tmp) / "2026-05-23"
            data_file = work_dir / "goldilocks" / "data" / "part.dat"
            data_file.parent.mkdir(parents=True)
            data_file.write_text("payload", encoding="utf-8")

            manifest = build_backup_manifest(
                work_dir,
                date(2026, 5, 23),
                manifest_base_path=final_dir,
            )

        self.assertEqual(str(final_dir), manifest.base_path)
        self.assertEqual(
            ["goldilocks/data/part.dat"],
            [item.relative_path for item in manifest.files],
        )

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

    def test_restore_check_detects_manifest_checksum_mismatch_when_present(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            data_file = base / "goldilocks" / "data" / "part.dat"
            data_file.parent.mkdir(parents=True)
            data_file.write_text("payload", encoding="utf-8")
            manifest = build_backup_manifest(base, date(2026, 5, 23))
            manifest_path = base / "manifest.json"
            write_backup_manifest(manifest, manifest_path)
            (base / "manifest.sha256").write_text("0" * 64, encoding="utf-8")

            result = restore_check(manifest_path)

        self.assertEqual("failed", result.status)
        self.assertIn("manifest checksum mismatch", result.issues)

    def test_restore_check_accepts_matching_manifest_checksum_when_present(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            data_file = base / "goldilocks" / "data" / "part.dat"
            data_file.parent.mkdir(parents=True)
            data_file.write_text("payload", encoding="utf-8")
            manifest = build_backup_manifest(base, date(2026, 5, 23))
            manifest_path = base / "manifest.json"
            write_backup_manifest(manifest, manifest_path)
            (base / "manifest.sha256").write_text(
                "%s\n" % sha256_file(manifest_path),
                encoding="utf-8",
            )

            result = restore_check(manifest_path)

        self.assertEqual("ok", result.status)

    def test_restore_check_fails_for_empty_manifest_files(self):
        with TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "backup_date": "2026-05-23",
                        "dbms": "goldilocks",
                        "backup_policy": "weekly_goldilocks_full_backup",
                        "base_path": tmp,
                        "status": "success",
                        "files": [],
                    }
                ),
                encoding="utf-8",
            )

            result = restore_check(manifest_path)

        self.assertEqual("failed", result.status)
        self.assertIn("manifest has no backup files", result.issues)

    def test_restore_check_fails_for_invalid_manifest_json(self):
        with TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "manifest.json"
            manifest_path.write_text("{not-json", encoding="utf-8")

            result = restore_check(manifest_path)

        self.assertEqual("failed", result.status)
        self.assertIn("manifest is not valid json", result.issues)

    def test_restore_check_fails_when_manifest_root_is_not_object(self):
        with TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "manifest.json"
            manifest_path.write_text("[]", encoding="utf-8")

            result = restore_check(manifest_path)

        self.assertEqual("failed", result.status)
        self.assertIn("manifest root is not an object", result.issues)

    def test_backup_restore_status_critical_when_manifest_root_is_not_object(self):
        with TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "manifest.json"
            manifest_path.write_text("[]", encoding="utf-8")

            status = summarize_backup_restore_status(Path(tmp))

        self.assertEqual("critical", status.status)
        self.assertEqual("failed", status.restore_status)
        self.assertIn("manifest root is not an object", status.issues)

    def test_restore_check_fails_when_manifest_files_is_not_list(self):
        with TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "backup_date": "2026-05-23",
                        "dbms": "goldilocks",
                        "backup_policy": "weekly_goldilocks_full_backup",
                        "base_path": tmp,
                        "status": "success",
                        "files": "part.dat",
                    }
                ),
                encoding="utf-8",
            )

            result = restore_check(manifest_path)

        self.assertEqual("failed", result.status)
        self.assertIn("manifest files is not a list", result.issues)

    def test_restore_check_rejects_invalid_base_path_type(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp) / "backup"
            data = base / "goldilocks" / "data" / "part.dat"
            data.parent.mkdir(parents=True)
            data.write_text("payload", encoding="utf-8")
            manifest_path = base / "manifest.json"
            write_backup_manifest(
                build_backup_manifest(base, date(2026, 5, 23)),
                manifest_path,
            )
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload["base_path"] = ["bad"]
            manifest_path.write_text(json.dumps(payload), encoding="utf-8")

            result = restore_check(manifest_path)

        self.assertEqual("failed", result.status)
        self.assertIn("manifest base_path is invalid", result.issues)

    def test_restore_check_rejects_manifest_paths_that_escape_base(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp) / "backup"
            base.mkdir()
            outside = Path(tmp) / "outside.dat"
            outside.write_text("payload", encoding="utf-8")
            manifest_path = base / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "backup_date": "2026-05-23",
                        "dbms": "goldilocks",
                        "backup_policy": "weekly_goldilocks_full_backup",
                        "base_path": str(base),
                        "status": "success",
                        "files": [
                            {
                                "relative_path": "../outside.dat",
                                "size_bytes": outside.stat().st_size,
                                "sha256": "unused",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = restore_check(manifest_path)

        self.assertEqual("failed", result.status)
        self.assertIn("backup file path escapes base: ../outside.dat", result.issues)

    def test_restore_check_rejects_directory_manifest_entry(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            data_dir = base / "goldilocks" / "data"
            data_dir.mkdir(parents=True)
            manifest_path = base / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "backup_date": "2026-05-23",
                        "dbms": "goldilocks",
                        "backup_policy": "weekly_goldilocks_full_backup",
                        "base_path": str(base),
                        "status": "success",
                        "files": [
                            {
                                "relative_path": "goldilocks/data",
                                "size_bytes": 0,
                                "sha256": "unused",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = restore_check(manifest_path)

        self.assertEqual("failed", result.status)
        self.assertIn("backup path is not a file: goldilocks/data", result.issues)

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

            status = summarize_backup_restore_status(
                base,
                checked_at=datetime(2026, 5, 24, 10, 0, 0),
            )

        self.assertEqual("ok", status.status)
        self.assertEqual("success", status.backup_status)
        self.assertEqual("ok", status.restore_status)
        self.assertEqual(str(manifest_path), status.latest_manifest_path)

    def test_latest_manifest_ignores_in_progress_backup_manifest(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            current = base / "2026-05-22"
            current_data = current / "goldilocks" / "data" / "part.dat"
            current_data.parent.mkdir(parents=True)
            current_data.write_text("payload", encoding="utf-8")
            current_manifest = build_backup_manifest(current, date(2026, 5, 22))
            current_manifest_path = current / "manifest.json"
            write_backup_manifest(current_manifest, current_manifest_path)

            staged = base / ".2026-05-23.in_progress.123"
            staged_data = staged / "goldilocks" / "data" / "part.dat"
            staged_data.parent.mkdir(parents=True)
            staged_data.write_text("new-payload", encoding="utf-8")
            staged_manifest = build_backup_manifest(
                staged,
                date(2026, 5, 23),
                manifest_base_path=base / "2026-05-23",
            )
            write_backup_manifest(staged_manifest, staged / "manifest.json")

            latest = find_latest_backup_manifest(base)
            status = summarize_backup_restore_status(
                base,
                checked_at=datetime(2026, 5, 23, 10, 0, 0),
            )

        self.assertEqual(current_manifest_path, latest)
        self.assertEqual("ok", status.status)
        self.assertEqual(str(current_manifest_path), status.latest_manifest_path)

    def test_latest_manifest_ignores_nested_backup_content_manifest(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            current = base / "2026-05-22"
            current_data = current / "goldilocks" / "data" / "part.dat"
            current_data.parent.mkdir(parents=True)
            current_data.write_text("payload", encoding="utf-8")
            current_manifest = build_backup_manifest(current, date(2026, 5, 22))
            current_manifest_path = current / "manifest.json"
            write_backup_manifest(current_manifest, current_manifest_path)

            nested_manifest = base / "2026-05-23" / "goldilocks" / "manifest.json"
            nested_manifest.parent.mkdir(parents=True)
            nested_manifest.write_text("{not-json", encoding="utf-8")

            latest = find_latest_backup_manifest(base)
            status = summarize_backup_restore_status(
                base,
                checked_at=datetime(2026, 5, 23, 10, 0, 0),
            )

        self.assertEqual(current_manifest_path, latest)
        self.assertEqual("ok", status.status)
        self.assertEqual(str(current_manifest_path), status.latest_manifest_path)

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

    def test_backup_restore_status_degraded_for_stale_successful_manifest(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            data_file = base / "goldilocks" / "data" / "part.dat"
            data_file.parent.mkdir(parents=True)
            data_file.write_text("payload", encoding="utf-8")
            manifest = build_backup_manifest(
                base,
                date(2026, 5, 1),
                status="success",
            )
            manifest_path = base / "manifest.json"
            write_backup_manifest(manifest, manifest_path)

            status = summarize_backup_restore_status(
                base,
                checked_at=datetime(2026, 5, 23, 10, 0, 0),
            )

        self.assertEqual("degraded", status.status)
        self.assertEqual("ok", status.restore_status)
        self.assertIn("latest backup is stale: 22 days old", status.issues)

    def test_backup_restore_status_degraded_when_backup_date_missing(self):
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
            payload = manifest.as_dict()
            payload.pop("backup_date")
            manifest_path = base / "manifest.json"
            manifest_path.write_text(json.dumps(payload), encoding="utf-8")

            status = summarize_backup_restore_status(base)

        self.assertEqual("degraded", status.status)
        self.assertEqual("ok", status.restore_status)
        self.assertIn("latest backup date is missing", status.issues)

    def test_backup_restore_status_degraded_when_backup_date_invalid(self):
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
            payload = manifest.as_dict()
            payload["backup_date"] = "2026-99-99"
            manifest_path = base / "manifest.json"
            manifest_path.write_text(json.dumps(payload), encoding="utf-8")

            status = summarize_backup_restore_status(base)

        self.assertEqual("degraded", status.status)
        self.assertEqual("ok", status.restore_status)
        self.assertIn("latest backup date is invalid: 2026-99-99", status.issues)

    def test_backup_restore_status_critical_for_invalid_manifest(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            (base / "manifest.json").write_text("{not-json", encoding="utf-8")

            status = summarize_backup_restore_status(base)

        self.assertEqual("critical", status.status)
        self.assertEqual("failed", status.restore_status)
        self.assertEqual("unknown", status.backup_status)
        self.assertIn("manifest is not valid json", status.issues)

    def test_goldilocks_backup_script_skips_without_configured_command(self):
        with TemporaryDirectory() as tmp:
            result = self._run_backup_script(tmp)

            self.assertEqual(0, result.returncode)
            self.assertIn("set GOLDILOCKS_BACKUP_COMMAND", result.stderr)
            self.assertFalse((Path(tmp) / "2026-05-23" / "manifest.json").exists())
            self.assertFalse((Path(tmp) / ".goldilocks_backup.lock").exists())

    def test_goldilocks_backup_script_rejects_invalid_backup_date_before_lock(self):
        with TemporaryDirectory() as tmp:
            result = self._run_backup_script(
                tmp,
                backup_date="../bad",
                backup_command=(
                    "mkdir -p goldilocks/data && "
                    "printf payload > goldilocks/data/part.dat"
                ),
            )

            self.assertNotEqual(0, result.returncode)
            self.assertIn("BACKUP_DATE must be an ISO date", result.stderr)
            self.assertFalse((Path(tmp) / ".goldilocks_backup.lock").exists())
            self.assertFalse((Path(tmp) / "bad" / "manifest.json").exists())

    def test_goldilocks_backup_script_rejects_root_backup_base_dir(self):
        result = self._run_backup_script(
            "/",
            backup_command=(
                "mkdir -p goldilocks/data && "
                "printf payload > goldilocks/data/part.dat"
            ),
        )

        self.assertEqual(64, result.returncode)
        self.assertIn("BACKUP_BASE_DIR must not be /", result.stderr)

    def test_goldilocks_backup_script_runs_command_and_writes_restorable_manifest(self):
        with TemporaryDirectory() as tmp:
            result = self._run_backup_script(
                tmp,
                backup_command=(
                    "mkdir -p goldilocks/data && "
                    "printf payload > goldilocks/data/part.dat"
                ),
            )

            manifest_path = Path(tmp) / "2026-05-23" / "manifest.json"
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue(manifest_path.exists())
            self.assertTrue((Path(tmp) / "2026-05-23" / "manifest.sha256").exists())
            self.assertEqual("ok", restore_check(manifest_path).status)
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual("success", payload["status"])
            self.assertEqual(
                ["goldilocks/data/part.dat"],
                [item["relative_path"] for item in payload["files"]],
            )
            checksum = (Path(tmp) / "2026-05-23" / "manifest.sha256").read_text(
                encoding="utf-8"
            )
            self.assertEqual(64, len(checksum.strip()))
            self.assertNotIn("in_progress", checksum)
            self.assertFalse((Path(tmp) / ".goldilocks_backup.lock").exists())
            self.assertEqual([], list(Path(tmp).glob(".2026-05-23.in_progress.*")))

    def test_goldilocks_backup_script_releases_lock_when_command_fails(self):
        with TemporaryDirectory() as tmp:
            result = self._run_backup_script(tmp, backup_command="exit 42")

            self.assertEqual(42, result.returncode)
            self.assertFalse((Path(tmp) / ".goldilocks_backup.lock").exists())
            self.assertFalse((Path(tmp) / "2026-05-23" / "manifest.json").exists())
            self.assertEqual([], list(Path(tmp).glob(".2026-05-23.in_progress.*")))

    def test_goldilocks_backup_script_keeps_existing_backup_when_command_fails(self):
        with TemporaryDirectory() as tmp:
            existing_target = Path(tmp) / "2026-05-23"
            existing_target.mkdir()
            existing_manifest = existing_target / "manifest.json"
            existing_manifest.write_text("old-manifest", encoding="utf-8")

            result = self._run_backup_script(tmp, backup_command="exit 42")

            self.assertEqual(42, result.returncode)
            self.assertEqual("old-manifest", existing_manifest.read_text(encoding="utf-8"))
            self.assertFalse((Path(tmp) / ".goldilocks_backup.lock").exists())
            self.assertEqual([], list(Path(tmp).glob(".2026-05-23.in_progress.*")))

    def test_goldilocks_backup_script_replaces_existing_backup_after_success(self):
        with TemporaryDirectory() as tmp:
            existing_target = Path(tmp) / "2026-05-23"
            existing_target.mkdir()
            (existing_target / "old.dat").write_text("old", encoding="utf-8")

            result = self._run_backup_script(
                tmp,
                backup_command=(
                    "mkdir -p goldilocks/data && "
                    "printf new > goldilocks/data/part.dat"
                ),
            )

            manifest_path = existing_target / "manifest.json"
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertFalse((existing_target / "old.dat").exists())
            self.assertEqual("ok", restore_check(manifest_path).status)
            self.assertEqual(
                "new",
                (existing_target / "goldilocks" / "data" / "part.dat").read_text(
                    encoding="utf-8"
                ),
            )
            self.assertEqual([], list(Path(tmp).glob(".2026-05-23.in_progress.*")))

    def test_goldilocks_backup_script_rejects_empty_successful_backup(self):
        with TemporaryDirectory() as tmp:
            result = self._run_backup_script(tmp, backup_command="true")

            self.assertNotEqual(0, result.returncode)
            self.assertIn("backup command produced no files", result.stderr)
            self.assertFalse((Path(tmp) / ".goldilocks_backup.lock").exists())
            self.assertFalse((Path(tmp) / "2026-05-23" / "manifest.json").exists())
            self.assertEqual([], list(Path(tmp).glob(".2026-05-23.in_progress.*")))

    def test_goldilocks_backup_script_exits_when_lock_is_already_held(self):
        with TemporaryDirectory() as tmp:
            lock_dir = Path(tmp) / ".goldilocks_backup.lock"
            lock_dir.mkdir()
            result = self._run_backup_script(
                tmp,
                backup_command=(
                    "mkdir -p goldilocks/data && "
                    "printf payload > goldilocks/data/part.dat"
                ),
            )

            self.assertEqual(75, result.returncode)
            self.assertIn("another backup appears to be running", result.stderr)
            self.assertTrue(lock_dir.exists())
            self.assertFalse((Path(tmp) / "2026-05-23" / "manifest.json").exists())

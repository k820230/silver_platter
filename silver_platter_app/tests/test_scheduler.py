from datetime import date, datetime
from pathlib import Path
from subprocess import CompletedProcess
from tempfile import TemporaryDirectory
from unittest import TestCase

from silver_platter.backup import build_backup_manifest, write_backup_manifest
from silver_platter.worker.scheduler import (
    MVP_BACKUP_SCHEDULE,
    MVP_RESTORE_DRILL_SCHEDULE,
    MonthlySchedule,
    latest_weekly_run_at,
    next_monthly_run_after,
    next_weekly_run_after,
    run_due_backup_once,
    scheduler_now,
    scheduler_timezone,
)


class SchedulerTests(TestCase):
    def test_next_weekly_run_after_returns_same_saturday_when_before_10(self):
        result = next_weekly_run_after(datetime(2026, 5, 23, 9, 0, 0), MVP_BACKUP_SCHEDULE)

        self.assertEqual(datetime(2026, 5, 23, 10, 0, 0), result)

    def test_next_weekly_run_after_returns_next_saturday_when_after_10(self):
        result = next_weekly_run_after(datetime(2026, 5, 23, 10, 1, 0), MVP_BACKUP_SCHEDULE)

        self.assertEqual(datetime(2026, 5, 30, 10, 0, 0), result)

    def test_latest_weekly_run_at_returns_previous_saturday_before_schedule(self):
        result = latest_weekly_run_at(datetime(2026, 5, 23, 9, 0, 0), MVP_BACKUP_SCHEDULE)

        self.assertEqual(datetime(2026, 5, 16, 10, 0, 0), result)

    def test_latest_weekly_run_at_returns_same_saturday_after_schedule(self):
        result = latest_weekly_run_at(datetime(2026, 5, 23, 10, 1, 0), MVP_BACKUP_SCHEDULE)

        self.assertEqual(datetime(2026, 5, 23, 10, 0, 0), result)

    def test_next_weekly_run_after_preserves_timezone(self):
        timezone = scheduler_timezone("Asia/Seoul")
        result = next_weekly_run_after(
            datetime(2026, 5, 23, 9, 0, 0, tzinfo=timezone),
            MVP_BACKUP_SCHEDULE,
        )

        self.assertEqual("2026-05-23T10:00:00+09:00", result.isoformat())
        self.assertIs(timezone, result.tzinfo)

    def test_next_monthly_run_after_returns_same_day_when_before_schedule(self):
        result = next_monthly_run_after(
            datetime(2026, 5, 1, 10, 0, 0),
            MVP_RESTORE_DRILL_SCHEDULE,
        )

        self.assertEqual(datetime(2026, 5, 1, 11, 0, 0), result)

    def test_next_monthly_run_after_returns_next_month_when_after_schedule(self):
        result = next_monthly_run_after(
            datetime(2026, 5, 1, 11, 1, 0),
            MVP_RESTORE_DRILL_SCHEDULE,
        )

        self.assertEqual(datetime(2026, 6, 1, 11, 0, 0), result)

    def test_next_monthly_run_after_clamps_to_last_day_of_short_month(self):
        result = next_monthly_run_after(
            datetime(2026, 1, 31, 10, 1, 0),
            MonthlySchedule(day=31, hour=10, minute=0, timezone="Asia/Seoul"),
        )

        self.assertEqual(datetime(2026, 2, 28, 10, 0, 0), result)

    def test_scheduler_now_uses_configured_timezone(self):
        result = scheduler_now("Asia/Seoul")

        self.assertEqual("Asia/Seoul", result.tzinfo.tzname(result))

    def test_scheduler_timezone_rejects_unknown_timezone(self):
        with self.assertRaises(ValueError):
            scheduler_timezone("America/New_York")

    def test_run_due_backup_once_skips_when_scheduled_manifest_exists(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            data = base / "goldilocks" / "data" / "part.dat"
            data.parent.mkdir(parents=True)
            data.write_text("payload", encoding="utf-8")
            write_backup_manifest(
                build_backup_manifest(base, date(2026, 5, 23)),
                base / "manifest.json",
            )
            calls = []

            def runner(*args, **kwargs):
                calls.append((args, kwargs))
                return CompletedProcess(args[0], 0, stdout="ran", stderr="")

            result = run_due_backup_once(
                datetime(2026, 5, 23, 12, 0, 0),
                base,
                backup_script=base / "goldilocks_backup.sh",
                runner=runner,
            )

        self.assertEqual("skipped", result.status)
        self.assertEqual("backup already exists for 2026-05-23", result.detail)
        self.assertEqual([], calls)

    def test_run_due_backup_once_runs_backup_script_for_missing_manifest(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            seen = {}

            def runner(args, cwd, env, capture_output, text):
                seen["args"] = args
                seen["cwd"] = cwd
                seen["backup_base_dir"] = env["BACKUP_BASE_DIR"]
                seen["backup_date"] = env["BACKUP_DATE"]
                seen["capture_output"] = capture_output
                seen["text"] = text
                data = base / "goldilocks" / "data" / "part.dat"
                data.parent.mkdir(parents=True)
                data.write_text("payload", encoding="utf-8")
                write_backup_manifest(
                    build_backup_manifest(base, date(2026, 5, 23)),
                    base / "manifest.json",
                )
                return CompletedProcess(args, 0, stdout="backup complete", stderr="")

            result = run_due_backup_once(
                datetime(2026, 5, 23, 12, 0, 0),
                base,
                backup_script=base / "scripts" / "goldilocks_backup.sh",
                runner=runner,
            )

        self.assertEqual("completed", result.status)
        self.assertEqual(0, result.exit_code)
        self.assertEqual(["bash", str(base / "scripts" / "goldilocks_backup.sh")], seen["args"])
        self.assertEqual(str(base), seen["backup_base_dir"])
        self.assertEqual("2026-05-23", seen["backup_date"])
        self.assertTrue(seen["capture_output"])
        self.assertTrue(seen["text"])

    def test_run_due_backup_once_reports_skip_when_wrapper_makes_no_manifest(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)

            def runner(args, **kwargs):
                return CompletedProcess(args, 0, stdout="", stderr="Goldilocks backup skipped")

            result = run_due_backup_once(
                datetime(2026, 5, 23, 12, 0, 0),
                base,
                backup_script=base / "scripts" / "goldilocks_backup.sh",
                runner=runner,
            )

        self.assertEqual("skipped", result.status)
        self.assertEqual(0, result.exit_code)
        self.assertIn("Goldilocks backup skipped", result.detail)

    def test_run_due_backup_once_reports_failure(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)

            def runner(args, **kwargs):
                return CompletedProcess(args, 42, stdout="", stderr="backup failed")

            result = run_due_backup_once(
                datetime(2026, 5, 23, 12, 0, 0),
                base,
                backup_script=base / "scripts" / "goldilocks_backup.sh",
                runner=runner,
            )

        self.assertEqual("failed", result.status)
        self.assertEqual(42, result.exit_code)
        self.assertEqual("backup failed", result.detail)

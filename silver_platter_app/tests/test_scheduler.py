from datetime import datetime
from unittest import TestCase

from silver_platter.worker.scheduler import (
    MVP_BACKUP_SCHEDULE,
    MVP_RESTORE_DRILL_SCHEDULE,
    MonthlySchedule,
    next_monthly_run_after,
    next_weekly_run_after,
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

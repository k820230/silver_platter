from datetime import datetime
from unittest import TestCase

from silver_platter.worker.scheduler import MVP_BACKUP_SCHEDULE, next_weekly_run_after


class SchedulerTests(TestCase):
    def test_next_weekly_run_after_returns_same_saturday_when_before_10(self):
        result = next_weekly_run_after(datetime(2026, 5, 23, 9, 0, 0), MVP_BACKUP_SCHEDULE)

        self.assertEqual(datetime(2026, 5, 23, 10, 0, 0), result)

    def test_next_weekly_run_after_returns_next_saturday_when_after_10(self):
        result = next_weekly_run_after(datetime(2026, 5, 23, 10, 1, 0), MVP_BACKUP_SCHEDULE)

        self.assertEqual(datetime(2026, 5, 30, 10, 0, 0), result)

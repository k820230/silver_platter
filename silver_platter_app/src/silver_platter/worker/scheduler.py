from dataclasses import dataclass
import calendar
from datetime import datetime, timedelta

from silver_platter.config import AppSettings


@dataclass(frozen=True)
class WeeklySchedule:
    weekday: int
    hour: int
    minute: int
    timezone: str


@dataclass(frozen=True)
class MonthlySchedule:
    day: int
    hour: int
    minute: int
    timezone: str


MVP_BACKUP_SCHEDULE = WeeklySchedule(
    weekday=5,
    hour=10,
    minute=0,
    timezone="Asia/Seoul",
)

MVP_RESTORE_DRILL_SCHEDULE = MonthlySchedule(
    day=1,
    hour=11,
    minute=0,
    timezone="Asia/Seoul",
)


def next_weekly_run_after(now: datetime, schedule: WeeklySchedule = MVP_BACKUP_SCHEDULE) -> datetime:
    candidate = now.replace(
        hour=schedule.hour,
        minute=schedule.minute,
        second=0,
        microsecond=0,
    )
    days_until = (schedule.weekday - now.weekday()) % 7
    candidate = candidate + timedelta(days=days_until)
    if candidate <= now:
        candidate = candidate + timedelta(days=7)
    return candidate


def _scheduled_day(year: int, month: int, requested_day: int) -> int:
    if requested_day < 1:
        raise ValueError("monthly schedule day must be positive")
    last_day = calendar.monthrange(year, month)[1]
    return min(requested_day, last_day)


def _add_month(year: int, month: int) -> tuple:
    if month == 12:
        return year + 1, 1
    return year, month + 1


def next_monthly_run_after(
    now: datetime,
    schedule: MonthlySchedule = MVP_RESTORE_DRILL_SCHEDULE,
) -> datetime:
    candidate = now.replace(
        day=_scheduled_day(now.year, now.month, schedule.day),
        hour=schedule.hour,
        minute=schedule.minute,
        second=0,
        microsecond=0,
    )
    if candidate <= now:
        year, month = _add_month(now.year, now.month)
        candidate = now.replace(
            year=year,
            month=month,
            day=_scheduled_day(year, month, schedule.day),
            hour=schedule.hour,
            minute=schedule.minute,
            second=0,
            microsecond=0,
        )
    return candidate


def main() -> None:
    settings = AppSettings.from_env()
    now = datetime.utcnow()
    next_backup = next_weekly_run_after(now)
    next_restore_drill = next_monthly_run_after(now)
    print(
        "silver_platter scheduler ready timezone=%s backup_base_dir=%s now=%s next_backup=%s next_restore_drill=%s"
        % (
            settings.app_timezone,
            settings.backup_base_dir,
            now.isoformat(),
            next_backup.isoformat(),
            next_restore_drill.isoformat(),
        )
    )


if __name__ == "__main__":
    main()

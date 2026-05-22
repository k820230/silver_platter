from dataclasses import dataclass
from datetime import datetime, timedelta

from silver_platter.config import AppSettings


@dataclass(frozen=True)
class WeeklySchedule:
    weekday: int
    hour: int
    minute: int
    timezone: str


MVP_BACKUP_SCHEDULE = WeeklySchedule(
    weekday=5,
    hour=10,
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


def main() -> None:
    settings = AppSettings.from_env()
    next_backup = next_weekly_run_after(datetime.utcnow())
    print(
        "silver_platter scheduler ready timezone=%s backup_base_dir=%s now=%s next_backup=%s"
        % (
            settings.app_timezone,
            settings.backup_base_dir,
            datetime.utcnow().isoformat(),
            next_backup.isoformat(),
        )
    )


if __name__ == "__main__":
    main()

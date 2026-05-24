from dataclasses import dataclass
import calendar
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import subprocess
from typing import Callable, Dict, Optional

from silver_platter.backup import find_latest_backup_manifest, _read_manifest_payload
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


@dataclass(frozen=True)
class SchedulerJobResult:
    job: str
    status: str
    scheduled_at: datetime
    completed_at: datetime
    exit_code: Optional[int]
    detail: str


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


def latest_weekly_run_at(
    now: datetime,
    schedule: WeeklySchedule = MVP_BACKUP_SCHEDULE,
) -> datetime:
    candidate = now.replace(
        hour=schedule.hour,
        minute=schedule.minute,
        second=0,
        microsecond=0,
    )
    days_since = (now.weekday() - schedule.weekday) % 7
    candidate = candidate - timedelta(days=days_since)
    if candidate > now:
        candidate = candidate - timedelta(days=7)
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


def scheduler_timezone(timezone_name: str) -> timezone:
    if timezone_name == "Asia/Seoul":
        return timezone(timedelta(hours=9), timezone_name)
    if timezone_name in {"UTC", "Etc/UTC"}:
        return timezone.utc
    raise ValueError("unsupported scheduler timezone: %s" % timezone_name)


def scheduler_now(timezone_name: str) -> datetime:
    return datetime.now(scheduler_timezone(timezone_name))


def _backup_script_path() -> Path:
    return Path(__file__).resolve().parents[3] / "scripts" / "goldilocks_backup.sh"


def _latest_backup_date(backup_base_dir: Path) -> Optional[str]:
    manifest_path = find_latest_backup_manifest(backup_base_dir)
    if manifest_path is None:
        return None
    payload, _issues = _read_manifest_payload(manifest_path)
    if payload is None or payload.get("status") not in {"success", "ok"}:
        return None
    backup_date = payload.get("backup_date")
    return str(backup_date) if backup_date else None


def run_due_backup_once(
    now: datetime,
    backup_base_dir: Path,
    backup_script: Optional[Path] = None,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> SchedulerJobResult:
    scheduled_at = latest_weekly_run_at(now)
    scheduled_date = scheduled_at.date().isoformat()
    latest_backup_date = _latest_backup_date(backup_base_dir)
    if latest_backup_date == scheduled_date:
        return SchedulerJobResult(
            job="weekly_goldilocks_backup",
            status="skipped",
            scheduled_at=scheduled_at,
            completed_at=now,
            exit_code=None,
            detail="backup already exists for %s" % scheduled_date,
        )

    env: Dict[str, str] = {
        **os.environ,
        "BACKUP_BASE_DIR": str(backup_base_dir),
        "BACKUP_DATE": scheduled_date,
    }
    script = backup_script or _backup_script_path()
    completed = runner(
        ["bash", str(script)],
        cwd=str(script.parent.parent),
        env=env,
        capture_output=True,
        text=True,
    )
    output = (completed.stdout or completed.stderr or "").strip()
    if completed.returncode != 0:
        status = "failed"
    elif _latest_backup_date(backup_base_dir) == scheduled_date:
        status = "completed"
    else:
        status = "skipped"
    return SchedulerJobResult(
        job="weekly_goldilocks_backup",
        status=status,
        scheduled_at=scheduled_at,
        completed_at=scheduler_now(MVP_BACKUP_SCHEDULE.timezone),
        exit_code=completed.returncode,
        detail=output,
    )


def main() -> None:
    settings = AppSettings.from_env()
    now = scheduler_now(settings.app_timezone)
    next_backup = next_weekly_run_after(now)
    next_restore_drill = next_monthly_run_after(now)
    backup_result = run_due_backup_once(now, Path(settings.backup_base_dir))
    print(
        "silver_platter scheduler ready timezone=%s backup_base_dir=%s now=%s next_backup=%s next_restore_drill=%s backup_job=%s"
        % (
            settings.app_timezone,
            settings.backup_base_dir,
            now.isoformat(),
            next_backup.isoformat(),
            next_restore_drill.isoformat(),
            backup_result,
        )
    )


if __name__ == "__main__":
    main()

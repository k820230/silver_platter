from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class BackupFileEntry:
    relative_path: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class BackupManifest:
    backup_date: date
    dbms: str
    backup_policy: str
    base_path: str
    status: str
    files: List[BackupFileEntry]
    created_at: datetime

    def as_dict(self) -> dict:
        return {
            "backup_date": self.backup_date.isoformat(),
            "dbms": self.dbms,
            "backup_policy": self.backup_policy,
            "base_path": self.base_path,
            "status": self.status,
            "files": [entry.__dict__ for entry in self.files],
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True)
class RestoreCheckResult:
    status: str
    checked_at: datetime
    manifest_path: str
    issue_count: int
    issues: List[str]


@dataclass(frozen=True)
class BackupRestoreStatus:
    status: str
    backup_base_dir: str
    latest_manifest_path: Optional[str]
    latest_backup_date: Optional[str]
    backup_status: str
    restore_status: str
    lock_held: bool
    checked_at: datetime
    issue_count: int
    issues: List[str]

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "backup_base_dir": self.backup_base_dir,
            "latest_manifest_path": self.latest_manifest_path,
            "latest_backup_date": self.latest_backup_date,
            "backup_status": self.backup_status,
            "restore_status": self.restore_status,
            "lock_held": self.lock_held,
            "checked_at": self.checked_at.isoformat(),
            "issue_count": self.issue_count,
            "issues": self.issues,
        }


class BackupExecutionLock:
    def __init__(
        self,
        lock_path: Path,
        owner_id: str,
        acquired_at: Optional[datetime] = None,
    ) -> None:
        self.lock_path = lock_path
        self.owner_id = owner_id
        self.acquired_at = acquired_at or datetime.utcnow()
        self.acquired = False

    def acquire(self) -> bool:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "owner_id": self.owner_id,
            "acquired_at": self.acquired_at.isoformat(),
        }
        try:
            descriptor = os.open(
                self.lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            )
        except FileExistsError:
            return False
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True)
            handle.write("\n")
        self.acquired = True
        return True

    def release(self) -> None:
        if not self.acquired:
            return
        try:
            self.lock_path.unlink()
        except FileNotFoundError:
            pass
        self.acquired = False

    def __enter__(self) -> "BackupExecutionLock":
        if not self.acquire():
            raise RuntimeError("backup execution lock is already held: %s" % self.lock_path)
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.release()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_backup_manifest(
    base_path: Path,
    backup_date: date,
    policy_code: str = "weekly_goldilocks_full_backup",
    dbms: str = "goldilocks",
    status: str = "success",
    created_at: Optional[datetime] = None,
    manifest_base_path: Optional[Path] = None,
) -> BackupManifest:
    files: List[BackupFileEntry] = []
    excluded_names = {"manifest.json", "manifest.sha256", "checksum.sha256"}
    for path in sorted(base_path.rglob("*")):
        if not path.is_file() or path.name in excluded_names:
            continue
        files.append(
            BackupFileEntry(
                relative_path=str(path.relative_to(base_path)),
                size_bytes=path.stat().st_size,
                sha256=sha256_file(path),
            )
        )
    return BackupManifest(
        backup_date=backup_date,
        dbms=dbms,
        backup_policy=policy_code,
        base_path=str(manifest_base_path or base_path),
        status=status,
        files=files,
        created_at=created_at or datetime.utcnow(),
    )


def write_backup_manifest(manifest: BackupManifest, manifest_path: Path) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest.as_dict(), sort_keys=True, indent=2),
        encoding="utf-8",
    )


def _manifest_sort_key(path: Path) -> tuple:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        backup_date = str(payload.get("backup_date", ""))
        created_at = str(payload.get("created_at", ""))
        return backup_date, created_at, str(path)
    except (OSError, json.JSONDecodeError):
        return "", "", str(path)


def _is_in_progress_backup_path(path: Path) -> bool:
    return any(".in_progress." in part for part in path.parts)


def find_latest_backup_manifest(base_path: Path) -> Optional[Path]:
    if not base_path.exists():
        return None
    manifests = sorted(
        [
            path
            for path in base_path.rglob("manifest.json")
            if not _is_in_progress_backup_path(path)
        ],
        key=_manifest_sort_key,
    )
    return manifests[-1] if manifests else None


def _read_manifest_payload(manifest_path: Path) -> Tuple[Optional[Dict[str, object]], List[str]]:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except OSError as exc:
        return None, ["manifest cannot be read: %s" % exc]
    except json.JSONDecodeError:
        return None, ["manifest is not valid json"]
    if not isinstance(payload, dict):
        return None, ["manifest root is not an object"]
    return payload, []


def restore_check(manifest_path: Path) -> RestoreCheckResult:
    issues: List[str] = []
    if not manifest_path.exists():
        return RestoreCheckResult(
            status="failed",
            checked_at=datetime.utcnow(),
            manifest_path=str(manifest_path),
            issue_count=1,
            issues=["manifest is missing"],
        )
    payload, manifest_issues = _read_manifest_payload(manifest_path)
    if payload is None:
        return RestoreCheckResult(
            status="failed",
            checked_at=datetime.utcnow(),
            manifest_path=str(manifest_path),
            issue_count=len(manifest_issues),
            issues=manifest_issues,
        )
    manifest_checksum_path = manifest_path.with_name("manifest.sha256")
    if manifest_checksum_path.exists():
        try:
            expected_manifest_checksum = manifest_checksum_path.read_text(
                encoding="utf-8"
            ).strip().split()[0]
        except (IndexError, OSError):
            expected_manifest_checksum = ""
        if expected_manifest_checksum != sha256_file(manifest_path):
            issues.append("manifest checksum mismatch")
    base_path = Path(payload.get("base_path", manifest_path.parent))
    base_path_resolved = base_path.resolve(strict=False)
    if payload.get("dbms") != "goldilocks":
        issues.append("manifest dbms is not goldilocks")
    files = payload.get("files", [])
    if not isinstance(files, list):
        issues.append("manifest files is not a list")
        files = []
    if not files:
        issues.append("manifest has no backup files")
    for entry in files:
        if not isinstance(entry, dict):
            issues.append("manifest file entry is not an object")
            continue
        relative_path = str(entry.get("relative_path", ""))
        path = (base_path / relative_path).resolve(strict=False)
        try:
            path.relative_to(base_path_resolved)
        except ValueError:
            issues.append("backup file path escapes base: %s" % relative_path)
            continue
        if not path.exists():
            issues.append("missing backup file: %s" % relative_path)
            continue
        if not path.is_file():
            issues.append("backup path is not a file: %s" % relative_path)
            continue
        if path.stat().st_size != entry.get("size_bytes"):
            issues.append("size mismatch: %s" % relative_path)
        if sha256_file(path) != entry.get("sha256"):
            issues.append("checksum mismatch: %s" % relative_path)
    return RestoreCheckResult(
        status="ok" if not issues else "failed",
        checked_at=datetime.utcnow(),
        manifest_path=str(manifest_path),
        issue_count=len(issues),
        issues=issues,
    )


def summarize_backup_restore_status(
    backup_base_dir: Path,
    lock_path: Optional[Path] = None,
    checked_at: Optional[datetime] = None,
    max_backup_age_days: int = 8,
) -> BackupRestoreStatus:
    checked = checked_at or datetime.utcnow()
    lock_target = lock_path or (backup_base_dir / ".goldilocks_backup.lock")
    lock_held = lock_target.exists()
    issues: List[str] = []
    latest_manifest = find_latest_backup_manifest(backup_base_dir)
    if latest_manifest is None:
        issues.append("backup manifest is missing")
        return BackupRestoreStatus(
            status="degraded",
            backup_base_dir=str(backup_base_dir),
            latest_manifest_path=None,
            latest_backup_date=None,
            backup_status="missing",
            restore_status="not_checked",
            lock_held=lock_held,
            checked_at=checked,
            issue_count=len(issues),
            issues=issues,
        )

    restore_result = restore_check(latest_manifest)
    payload, _manifest_issues = _read_manifest_payload(latest_manifest)
    if payload is None:
        backup_status = "unknown"
        latest_backup_date = None
    else:
        backup_status = str(payload.get("status", "unknown"))
        latest_backup_date = payload.get("backup_date")
    issues.extend(restore_result.issues)
    if payload is not None:
        if not latest_backup_date:
            issues.append("latest backup date is missing")
        else:
            try:
                backup_age_days = (
                    checked.date() - date.fromisoformat(str(latest_backup_date))
                ).days
            except ValueError:
                issues.append("latest backup date is invalid: %s" % latest_backup_date)
            else:
                if backup_age_days > max_backup_age_days:
                    issues.append("latest backup is stale: %s days old" % backup_age_days)
    if backup_status not in {"success", "ok"}:
        issues.append("latest backup status is %s" % backup_status)

    if restore_result.status == "failed":
        status = "critical"
    elif issues:
        status = "degraded"
    else:
        status = "ok"

    return BackupRestoreStatus(
        status=status,
        backup_base_dir=str(backup_base_dir),
        latest_manifest_path=str(latest_manifest),
        latest_backup_date=latest_backup_date,
        backup_status=backup_status,
        restore_status=restore_result.status,
        lock_held=lock_held,
        checked_at=checked,
        issue_count=len(issues),
        issues=issues,
    )

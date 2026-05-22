from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import json
import os
from pathlib import Path
from typing import List, Optional


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
) -> BackupManifest:
    files: List[BackupFileEntry] = []
    for path in sorted(base_path.rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
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
        base_path=str(base_path),
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


def find_latest_backup_manifest(base_path: Path) -> Optional[Path]:
    if not base_path.exists():
        return None
    manifests = sorted(base_path.rglob("manifest.json"), key=_manifest_sort_key)
    return manifests[-1] if manifests else None


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
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    base_path = Path(payload.get("base_path", manifest_path.parent))
    if payload.get("dbms") != "goldilocks":
        issues.append("manifest dbms is not goldilocks")
    for entry in payload.get("files", []):
        path = base_path / entry.get("relative_path", "")
        if not path.exists():
            issues.append("missing backup file: %s" % entry.get("relative_path"))
            continue
        if path.stat().st_size != entry.get("size_bytes"):
            issues.append("size mismatch: %s" % entry.get("relative_path"))
        if sha256_file(path) != entry.get("sha256"):
            issues.append("checksum mismatch: %s" % entry.get("relative_path"))
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

    payload = json.loads(latest_manifest.read_text(encoding="utf-8"))
    backup_status = str(payload.get("status", "unknown"))
    restore_result = restore_check(latest_manifest)
    issues.extend(restore_result.issues)
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
        latest_backup_date=payload.get("backup_date"),
        backup_status=backup_status,
        restore_status=restore_result.status,
        lock_held=lock_held,
        checked_at=checked,
        issue_count=len(issues),
        issues=issues,
    )

from dataclasses import dataclass
from datetime import date, datetime
import hashlib
import json
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

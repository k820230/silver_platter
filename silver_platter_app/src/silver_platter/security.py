from dataclasses import dataclass
import os
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


@dataclass(frozen=True)
class SecurityCheckResult:
    status: str
    detail: str


@dataclass(frozen=True)
class PortExposure:
    host: str
    port: int
    purpose: str


DEFAULT_PERMISSION_MATRIX: Dict[str, Tuple[str, ...]] = {
    "viewer": ("read_dashboard", "read_audit"),
    "trader": ("read_dashboard", "read_audit", "submit_paper_order"),
    "risk_manager": (
        "read_dashboard",
        "read_audit",
        "submit_paper_order",
        "approve_risk_override",
        "toggle_kill_switch",
    ),
    "operator": (
        "read_dashboard",
        "read_audit",
        "run_backup",
        "run_restore_drill",
        "acknowledge_alert",
    ),
}


def role_allows(role: str, permission: str) -> bool:
    return permission in DEFAULT_PERMISSION_MATRIX.get(role, ())


def check_writable_directory(path: Path, create: bool = False) -> SecurityCheckResult:
    if create:
        path.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        return SecurityCheckResult("failed", "path does not exist: %s" % path)
    if not path.is_dir():
        return SecurityCheckResult("failed", "path is not a directory: %s" % path)
    writable = os.access(path, os.R_OK | os.W_OK | os.X_OK)
    return SecurityCheckResult(
        "pass" if writable else "failed",
        "directory is readable/writable/executable" if writable else "directory permissions are insufficient",
    )


def check_backup_access(path: Path) -> SecurityCheckResult:
    return check_writable_directory(path, create=False)


def validate_external_port_exposure(
    exposures: Iterable[PortExposure],
    allowed_hosts: Tuple[str, ...] = ("127.0.0.1", "localhost"),
) -> SecurityCheckResult:
    issues: List[str] = []
    for exposure in exposures:
        if exposure.host not in allowed_hosts:
            issues.append("%s:%s %s" % (exposure.host, exposure.port, exposure.purpose))
    if issues:
        return SecurityCheckResult("failed", "external ports exposed: %s" % "; ".join(issues))
    return SecurityCheckResult("pass", "all exposed ports are loopback-bound")


def assess_https_requirement(
    external_access_enabled: bool,
    https_enabled: bool,
) -> SecurityCheckResult:
    if external_access_enabled and not https_enabled:
        return SecurityCheckResult("failed", "HTTPS is required for external access")
    if external_access_enabled:
        return SecurityCheckResult("pass", "HTTPS enabled for external access")
    return SecurityCheckResult("pass", "external access disabled")

from dataclasses import dataclass
from datetime import datetime
import shutil
from typing import Callable, Dict, Iterable, List, Optional

from silver_platter.providers import (
    ProviderLicensePolicy,
    ProviderMetadata,
    license_policy_from_provider,
)


@dataclass(frozen=True)
class ComponentStatus:
    component: str
    status: str
    detail: str
    checked_at: datetime


@dataclass(frozen=True)
class OperationsSummary:
    status: str
    components: List[ComponentStatus]
    generated_at: datetime
    open_issue_count: int

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "generated_at": self.generated_at.isoformat(),
            "open_issue_count": self.open_issue_count,
            "components": [
                {
                    "component": component.component,
                    "status": component.status,
                    "detail": component.detail,
                    "checked_at": component.checked_at.isoformat(),
                }
                for component in self.components
            ],
        }


def summarize_operations(
    components: Iterable[ComponentStatus], generated_at: Optional[datetime] = None
) -> OperationsSummary:
    component_list = sorted(list(components), key=lambda item: item.component)
    issue_count = len(
        [
            component
            for component in component_list
            if component.status not in {"ok", "pass", "ready"}
        ]
    )
    if any(component.status in {"failed", "critical", "block"} for component in component_list):
        status = "critical"
    elif issue_count:
        status = "degraded"
    else:
        status = "ok"
    return OperationsSummary(
        status=status,
        components=component_list,
        generated_at=generated_at or datetime.utcnow(),
        open_issue_count=issue_count,
    )


def provider_health_components(
    catalog: Iterable[ProviderMetadata],
    missing_credentials: Iterable[str] = (),
    failed_providers: Iterable[str] = (),
    license_policies: Iterable[ProviderLicensePolicy] = (),
    checked_at: Optional[datetime] = None,
) -> List[ComponentStatus]:
    missing = {item.strip().lower() for item in missing_credentials}
    failed = {item.strip().lower() for item in failed_providers}
    policies: Dict[str, ProviderLicensePolicy] = {
        policy.provider_code.lower(): policy for policy in license_policies
    }
    timestamp = checked_at or datetime.utcnow()
    components: List[ComponentStatus] = []
    for provider in catalog:
        identifier = "%s:%s" % (provider.provider_code, provider.provider_type)
        normalized_code = provider.provider_code.lower()
        normalized_identifier = identifier.lower()
        policy = policies.get(normalized_code) or license_policy_from_provider(provider)
        license_detail = (
            "license=%s store=%s transform=%s realtime=%s redistribute=%s priority=%s"
            % (
                policy.license_name,
                policy.can_store,
                policy.can_transform,
                policy.can_display_realtime,
                policy.can_redistribute,
                provider.priority,
            )
        )
        if normalized_code in failed or normalized_identifier in failed:
            status = "failed"
            detail = "provider smoke or last collection failed; %s" % license_detail
        elif not policy.can_store or not policy.can_transform:
            status = "block"
            detail = "license blocks storage or transformation; %s" % license_detail
        elif normalized_code in missing or normalized_identifier in missing:
            status = "degraded"
            detail = "credential or opt-in setting missing; %s" % license_detail
        else:
            status = "ready"
            detail = license_detail
        components.append(
            ComponentStatus(
                component="provider:%s" % identifier,
                status=status,
                detail=detail,
                checked_at=timestamp,
            )
        )
    return sorted(components, key=lambda item: item.component)


def redis_health_component(
    ping: Callable[[], bool],
    checked_at: Optional[datetime] = None,
) -> ComponentStatus:
    timestamp = checked_at or datetime.utcnow()
    try:
        healthy = bool(ping())
    except Exception as exc:
        return ComponentStatus("redis", "failed", "redis ping failed: %s" % exc, timestamp)
    return ComponentStatus(
        "redis",
        "ready" if healthy else "failed",
        "redis ping ok" if healthy else "redis ping returned false",
        timestamp,
    )


def worker_heartbeat_component(
    worker_id: str,
    last_seen_at: Optional[datetime],
    max_age_seconds: int = 120,
    checked_at: Optional[datetime] = None,
) -> ComponentStatus:
    timestamp = checked_at or datetime.utcnow()
    if last_seen_at is None:
        return ComponentStatus("worker:%s" % worker_id, "failed", "heartbeat missing", timestamp)
    age_seconds = (timestamp - last_seen_at).total_seconds()
    status = "ready" if age_seconds <= max_age_seconds else "degraded"
    return ComponentStatus(
        "worker:%s" % worker_id,
        status,
        "heartbeat_age_seconds=%.0f max_age_seconds=%s" % (age_seconds, max_age_seconds),
        timestamp,
    )


def broker_api_component(
    broker_code: str,
    reachable: bool,
    detail: str = "",
    checked_at: Optional[datetime] = None,
) -> ComponentStatus:
    return ComponentStatus(
        "broker:%s" % broker_code,
        "ready" if reachable else "degraded",
        detail or ("broker API reachable" if reachable else "broker API unreachable"),
        checked_at or datetime.utcnow(),
    )


def data_delay_component(
    dataset_name: str,
    latest_available_at: Optional[datetime],
    max_delay_seconds: int,
    checked_at: Optional[datetime] = None,
) -> ComponentStatus:
    timestamp = checked_at or datetime.utcnow()
    if latest_available_at is None:
        return ComponentStatus("data_delay:%s" % dataset_name, "failed", "no data available", timestamp)
    delay_seconds = (timestamp - latest_available_at).total_seconds()
    status = "ready" if delay_seconds <= max_delay_seconds else "degraded"
    return ComponentStatus(
        "data_delay:%s" % dataset_name,
        status,
        "delay_seconds=%.0f max_delay_seconds=%s" % (delay_seconds, max_delay_seconds),
        timestamp,
    )


def disk_usage_component(
    path: str,
    warning_used_ratio: float = 0.85,
    critical_used_ratio: float = 0.95,
    checked_at: Optional[datetime] = None,
) -> ComponentStatus:
    usage = shutil.disk_usage(path)
    used_ratio = (usage.total - usage.free) / usage.total if usage.total else 1.0
    if used_ratio >= critical_used_ratio:
        status = "critical"
    elif used_ratio >= warning_used_ratio:
        status = "degraded"
    else:
        status = "ready"
    return ComponentStatus(
        "disk:%s" % path,
        status,
        "used_ratio=%.4f free_bytes=%s total_bytes=%s" % (used_ratio, usage.free, usage.total),
        checked_at or datetime.utcnow(),
    )

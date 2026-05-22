from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional

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

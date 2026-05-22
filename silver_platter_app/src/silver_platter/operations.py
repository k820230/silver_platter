from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional


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

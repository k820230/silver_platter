from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterable, List, Optional


@dataclass(frozen=True)
class AuditEvent:
    actor_type: str
    actor_id: Optional[str]
    action_code: str
    target_type: str
    target_id: Optional[str]
    occurred_at: datetime
    detail: Dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "actor_type": self.actor_type,
            "actor_id": self.actor_id,
            "action_code": self.action_code,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "occurred_at": self.occurred_at.isoformat(),
            "detail": self.detail,
        }


@dataclass
class AuditLog:
    events: List[AuditEvent] = field(default_factory=list)

    def append(
        self,
        actor_type: str,
        action_code: str,
        target_type: str,
        actor_id: Optional[str] = None,
        target_id: Optional[str] = None,
        detail: Optional[Dict[str, str]] = None,
        occurred_at: Optional[datetime] = None,
    ) -> AuditEvent:
        event = AuditEvent(
            actor_type=actor_type,
            actor_id=actor_id,
            action_code=action_code,
            target_type=target_type,
            target_id=target_id,
            occurred_at=occurred_at or datetime.utcnow(),
            detail=detail or {},
        )
        self.events.append(event)
        return event

    def query(
        self,
        action_code: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
    ) -> List[AuditEvent]:
        return filter_audit_events(self.events, action_code, target_type, target_id)


def filter_audit_events(
    events: Iterable[AuditEvent],
    action_code: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
) -> List[AuditEvent]:
    selected = []
    for event in events:
        if action_code is not None and event.action_code != action_code:
            continue
        if target_type is not None and event.target_type != target_type:
            continue
        if target_id is not None and event.target_id != target_id:
            continue
        selected.append(event)
    return sorted(selected, key=lambda item: item.occurred_at)

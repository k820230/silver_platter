from dataclasses import dataclass, field
from datetime import datetime
import json
from typing import Any, Dict, Iterable, List, Optional


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
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        source: str = "",
        occurred_at: Optional[datetime] = None,
    ) -> AuditEvent:
        event_detail = dict(detail or {})
        if user_id:
            event_detail.setdefault("actor_user_id", user_id)
        if session_id:
            event_detail.setdefault("actor_session_id", session_id)
        if source:
            event_detail.setdefault("actor_source", source)
        event = AuditEvent(
            actor_type=actor_type,
            actor_id=actor_id or user_id or session_id,
            action_code=action_code,
            target_type=target_type,
            target_id=target_id,
            occurred_at=occurred_at or datetime.utcnow(),
            detail=event_detail,
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


def build_setting_change_detail(
    before: Dict[str, Any],
    after: Dict[str, Any],
) -> Dict[str, str]:
    changed_keys = [
        key
        for key in sorted(set(before.keys()) | set(after.keys()))
        if before.get(key) != after.get(key)
    ]
    return {
        "changed_keys": ",".join(changed_keys),
        "before": json.dumps(
            {key: before.get(key) for key in changed_keys},
            ensure_ascii=True,
            sort_keys=True,
        ),
        "after": json.dumps(
            {key: after.get(key) for key in changed_keys},
            ensure_ascii=True,
            sort_keys=True,
        ),
    }

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, FrozenSet, Optional, Tuple


ORDER_DRAFT = "draft"
ORDER_PREVIEWED = "previewed"
ORDER_SUBMITTED = "submitted"
ORDER_ACCEPTED = "accepted"
ORDER_PARTIALLY_FILLED = "partially_filled"
ORDER_FILLED = "filled"
ORDER_CANCEL_REQUESTED = "cancel_requested"
ORDER_CANCELLED = "cancelled"
ORDER_REJECTED = "rejected"
ORDER_EXPIRED = "expired"

TERMINAL_STATES: FrozenSet[str] = frozenset(
    {ORDER_FILLED, ORDER_CANCELLED, ORDER_REJECTED, ORDER_EXPIRED}
)

ALLOWED_TRANSITIONS: Dict[str, FrozenSet[str]] = {
    ORDER_DRAFT: frozenset({ORDER_PREVIEWED, ORDER_REJECTED, ORDER_EXPIRED}),
    ORDER_PREVIEWED: frozenset({ORDER_SUBMITTED, ORDER_REJECTED, ORDER_EXPIRED}),
    ORDER_SUBMITTED: frozenset(
        {
            ORDER_ACCEPTED,
            ORDER_PARTIALLY_FILLED,
            ORDER_FILLED,
            ORDER_REJECTED,
            ORDER_CANCEL_REQUESTED,
            ORDER_EXPIRED,
        }
    ),
    ORDER_ACCEPTED: frozenset(
        {
            ORDER_PARTIALLY_FILLED,
            ORDER_FILLED,
            ORDER_CANCEL_REQUESTED,
            ORDER_CANCELLED,
            ORDER_REJECTED,
            ORDER_EXPIRED,
        }
    ),
    ORDER_PARTIALLY_FILLED: frozenset(
        {ORDER_PARTIALLY_FILLED, ORDER_FILLED, ORDER_CANCEL_REQUESTED, ORDER_CANCELLED}
    ),
    ORDER_CANCEL_REQUESTED: frozenset(
        {ORDER_CANCELLED, ORDER_PARTIALLY_FILLED, ORDER_FILLED, ORDER_REJECTED}
    ),
}


@dataclass(frozen=True)
class OrderStateRecord:
    order_id: str
    state: str
    updated_at: datetime
    filled_quantity: float = 0.0
    last_reason: Optional[str] = None
    idempotency_key: Optional[str] = None

    @property
    def terminal(self) -> bool:
        return self.state in TERMINAL_STATES


@dataclass(frozen=True)
class OrderStateEvent:
    order_id: str
    from_state: str
    to_state: str
    occurred_at: datetime
    reason: Optional[str] = None
    filled_quantity_delta: float = 0.0


@dataclass(frozen=True)
class BrokerReconciliationSnapshot:
    order_id: str
    broker_status: str
    filled_quantity: float = 0.0
    reason: str = ""


@dataclass(frozen=True)
class IdempotencyDecision:
    accepted: bool
    duplicate: bool
    message: str
    existing_order_id: Optional[str] = None


@dataclass
class IdempotencyRegistry:
    _keys: Dict[str, str] = field(default_factory=dict)

    def reserve(self, key: str, order_id: str) -> IdempotencyDecision:
        normalized_key = key.strip()
        if not normalized_key:
            return IdempotencyDecision(False, False, "idempotency key is required")
        existing = self._keys.get(normalized_key)
        if existing is not None:
            return IdempotencyDecision(
                False,
                True,
                "duplicate idempotency key",
                existing_order_id=existing,
            )
        self._keys[normalized_key] = order_id
        return IdempotencyDecision(True, False, "reserved")


def initial_order_state(
    order_id: str,
    idempotency_key: Optional[str] = None,
    now: Optional[datetime] = None,
) -> OrderStateRecord:
    return OrderStateRecord(
        order_id=order_id,
        state=ORDER_DRAFT,
        updated_at=now or datetime.utcnow(),
        idempotency_key=idempotency_key,
    )


def transition_order_state(
    record: OrderStateRecord,
    to_state: str,
    reason: Optional[str] = None,
    filled_quantity_delta: float = 0.0,
    now: Optional[datetime] = None,
) -> Tuple[OrderStateRecord, OrderStateEvent]:
    if filled_quantity_delta < 0:
        raise ValueError("filled_quantity_delta cannot be negative")
    if record.terminal:
        raise ValueError("cannot transition from terminal state %s" % record.state)
    allowed = ALLOWED_TRANSITIONS.get(record.state, frozenset())
    if to_state not in allowed:
        raise ValueError("invalid order transition %s -> %s" % (record.state, to_state))
    occurred_at = now or datetime.utcnow()
    next_record = OrderStateRecord(
        order_id=record.order_id,
        state=to_state,
        updated_at=occurred_at,
        filled_quantity=round(record.filled_quantity + filled_quantity_delta, 8),
        last_reason=reason,
        idempotency_key=record.idempotency_key,
    )
    event = OrderStateEvent(
        order_id=record.order_id,
        from_state=record.state,
        to_state=to_state,
        occurred_at=occurred_at,
        reason=reason,
        filled_quantity_delta=filled_quantity_delta,
    )
    return next_record, event


def reconcile_broker_timeout(
    record: OrderStateRecord,
    snapshot: BrokerReconciliationSnapshot,
    now: Optional[datetime] = None,
) -> Tuple[OrderStateRecord, OrderStateEvent]:
    if snapshot.order_id != record.order_id:
        raise ValueError("broker reconciliation snapshot order_id must match order")
    normalized_status = snapshot.broker_status.strip().lower()
    status_map = {
        "accepted": ORDER_ACCEPTED,
        "open": ORDER_ACCEPTED,
        "submitted": ORDER_ACCEPTED,
        "partial": ORDER_PARTIALLY_FILLED,
        "partially_filled": ORDER_PARTIALLY_FILLED,
        "filled": ORDER_FILLED,
        "cancelled": ORDER_CANCELLED,
        "canceled": ORDER_CANCELLED,
        "rejected": ORDER_REJECTED,
        "expired": ORDER_EXPIRED,
    }
    if normalized_status not in status_map:
        raise ValueError("unsupported broker reconciliation status: %s" % snapshot.broker_status)
    filled_delta = max(0.0, snapshot.filled_quantity - record.filled_quantity)
    return transition_order_state(
        record,
        status_map[normalized_status],
        snapshot.reason or "broker_timeout_reconciliation",
        filled_quantity_delta=filled_delta,
        now=now,
    )

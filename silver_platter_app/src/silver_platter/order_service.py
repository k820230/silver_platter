from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from silver_platter.broker import BrokerAdapter, BrokerOrderRequest
from silver_platter.order_preview import OrderPreviewInput, create_order_preview
from silver_platter.order_state import (
    IdempotencyRegistry,
    OrderStateEvent,
    OrderStateRecord,
    initial_order_state,
    transition_order_state,
)


@dataclass(frozen=True)
class OrderSubmissionInput:
    order_id: str
    account_id: str
    security_id: str
    side: str
    order_type: str
    market: str
    current_price: float
    quantity: float
    avg_daily_turnover_20d_krw: float
    idempotency_key: str
    limit_price: Optional[float] = None


@dataclass(frozen=True)
class OrderSubmissionResult:
    accepted: bool
    reason: str
    preview: Dict[str, object]
    state: OrderStateRecord
    events: List[OrderStateEvent]
    broker_order_id: Optional[str] = None


class OrderSubmissionService:
    def __init__(self, broker: BrokerAdapter, idempotency: Optional[IdempotencyRegistry] = None):
        self.broker = broker
        self.idempotency = idempotency or IdempotencyRegistry()

    def submit(self, request: OrderSubmissionInput) -> OrderSubmissionResult:
        reservation = self.idempotency.reserve(request.idempotency_key, request.order_id)
        state = initial_order_state(request.order_id, request.idempotency_key)
        events: List[OrderStateEvent] = []
        preview = create_order_preview(
            OrderPreviewInput(
                account_id=request.account_id,
                security_id=request.security_id,
                side=request.side,
                order_type=request.order_type,
                market=request.market,
                current_price=request.current_price,
                quantity=request.quantity,
                avg_daily_turnover_20d_krw=request.avg_daily_turnover_20d_krw,
            )
        )
        state, event = transition_order_state(state, "previewed", now=datetime.utcnow())
        events.append(event)

        if not reservation.accepted:
            state, event = transition_order_state(state, "rejected", reservation.message)
            events.append(event)
            return OrderSubmissionResult(False, reservation.message, preview, state, events)

        if preview["risk_check"]["status"] == "block":
            state, event = transition_order_state(state, "rejected", "risk_block")
            events.append(event)
            return OrderSubmissionResult(False, "risk_block", preview, state, events)

        state, event = transition_order_state(state, "submitted")
        events.append(event)
        ack = self.broker.submit_order(
            BrokerOrderRequest(
                order_id=request.order_id,
                account_id=request.account_id,
                security_id=request.security_id,
                side=request.side,
                order_type=request.order_type,
                quantity=request.quantity,
                limit_price=request.limit_price,
                market=request.market,
                idempotency_key=request.idempotency_key,
            )
        )
        target_state = "accepted" if ack.accepted else "rejected"
        state, event = transition_order_state(state, target_state, ack.reason)
        events.append(event)
        return OrderSubmissionResult(
            accepted=ack.accepted,
            reason=ack.reason,
            preview=preview,
            state=state,
            events=events,
            broker_order_id=ack.broker_order_id,
        )

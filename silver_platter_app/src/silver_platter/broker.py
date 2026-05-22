from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class BrokerOrderRequest:
    order_id: str
    account_id: str
    security_id: str
    side: str
    order_type: str
    quantity: float
    limit_price: Optional[float] = None
    market: str = "KR"
    idempotency_key: Optional[str] = None


@dataclass(frozen=True)
class BrokerOrderAck:
    accepted: bool
    broker_order_id: Optional[str]
    status: str
    reason: str
    submitted_at: datetime
    broker_send_attempted: bool


class BrokerAdapter(ABC):
    @abstractmethod
    def submit_order(self, request: BrokerOrderRequest) -> BrokerOrderAck:
        raise NotImplementedError


class PaperBrokerAdapter(BrokerAdapter):
    def submit_order(self, request: BrokerOrderRequest) -> BrokerOrderAck:
        return BrokerOrderAck(
            accepted=True,
            broker_order_id="paper-%s" % request.order_id,
            status="accepted",
            reason="paper order accepted without live broker transmission",
            submitted_at=datetime.utcnow(),
            broker_send_attempted=False,
        )


class KoreaInvestmentBrokerAdapter(BrokerAdapter):
    def __init__(self, live_order_enabled: bool = False):
        self.live_order_enabled = live_order_enabled

    def submit_order(self, request: BrokerOrderRequest) -> BrokerOrderAck:
        if not self.live_order_enabled:
            return BrokerOrderAck(
                accepted=False,
                broker_order_id=None,
                status="rejected",
                reason="live Korea Investment order sending is disabled",
                submitted_at=datetime.utcnow(),
                broker_send_attempted=False,
            )
        return BrokerOrderAck(
            accepted=False,
            broker_order_id=None,
            status="rejected",
            reason="Korea Investment live adapter boundary is not implemented",
            submitted_at=datetime.utcnow(),
            broker_send_attempted=True,
        )

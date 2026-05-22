from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List

from silver_platter.accounting import (
    BuyExecution,
    FifoMatch,
    PositionLot,
    SellExecution,
    create_lot,
    match_sell_fifo,
)
from silver_platter.order_preview import OrderPreviewInput, create_order_preview


@dataclass
class VirtualAccount:
    account_id: str
    cash_krw: float = 100_000_000.0
    lots: List[PositionLot] = field(default_factory=list)
    realized_pnl_krw: float = 0.0


@dataclass(frozen=True)
class SimulatedExecutionResult:
    accepted: bool
    reason: str
    preview: Dict[str, object]
    fifo_matches: List[FifoMatch] = field(default_factory=list)
    realized_pnl_krw: float = 0.0


class SimulationEngine:
    def __init__(self, account: VirtualAccount):
        self.account = account
        self._sequence = 0

    def _next_transaction_id(self) -> str:
        self._sequence += 1
        return "sim-tx-%06d" % self._sequence

    def execute(
        self,
        security_id: str,
        side: str,
        market: str,
        order_type: str,
        price: float,
        quantity: float,
        avg_daily_turnover_20d_krw: float,
        trade_date: date,
    ) -> SimulatedExecutionResult:
        preview = create_order_preview(
            OrderPreviewInput(
                account_id=self.account.account_id,
                security_id=security_id,
                side=side,
                order_type=order_type,
                market=market,
                current_price=price,
                quantity=quantity,
                avg_daily_turnover_20d_krw=avg_daily_turnover_20d_krw,
            )
        )
        if preview["risk_check"]["status"] == "block":
            return SimulatedExecutionResult(False, "risk_block", preview)

        order_amount = float(preview["order_amount_krw"])
        slippage = float(preview["expected_slippage_krw"])
        transaction_id = self._next_transaction_id()
        if side.lower() == "buy":
            total_cost = order_amount + slippage
            if total_cost > self.account.cash_krw:
                return SimulatedExecutionResult(False, "cash_shortage", preview)
            self.account.cash_krw -= total_cost
            self.account.lots.append(
                create_lot(
                    BuyExecution(
                        transaction_id=transaction_id,
                        security_id=security_id,
                        quantity=quantity,
                        unit_cost_krw=price,
                        acquired_date=trade_date,
                        fee_krw=slippage,
                    )
                )
            )
            return SimulatedExecutionResult(True, "filled", preview)

        if side.lower() == "sell":
            matches, realized_pnl = match_sell_fifo(
                SellExecution(
                    transaction_id=transaction_id,
                    security_id=security_id,
                    quantity=quantity,
                    unit_price_krw=price,
                    realized_date=trade_date,
                    fee_krw=slippage,
                ),
                self.account.lots,
            )
            self.account.cash_krw += order_amount - slippage
            self.account.realized_pnl_krw += realized_pnl
            return SimulatedExecutionResult(
                True,
                "filled",
                preview,
                fifo_matches=matches,
                realized_pnl_krw=realized_pnl,
            )

        return SimulatedExecutionResult(False, "unsupported_side", preview)

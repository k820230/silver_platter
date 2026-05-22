from dataclasses import dataclass
from datetime import date
from typing import Iterable, List, Tuple


@dataclass(frozen=True)
class BuyExecution:
    transaction_id: str
    security_id: str
    quantity: float
    unit_cost_krw: float
    acquired_date: date
    fee_krw: float = 0.0
    tax_krw: float = 0.0


@dataclass
class PositionLot:
    lot_id: str
    buy_transaction_id: str
    security_id: str
    acquired_date: date
    original_quantity: float
    remaining_quantity: float
    unit_cost_krw: float


@dataclass(frozen=True)
class SellExecution:
    transaction_id: str
    security_id: str
    quantity: float
    unit_price_krw: float
    realized_date: date
    fee_krw: float = 0.0
    tax_krw: float = 0.0


@dataclass(frozen=True)
class FifoMatch:
    sell_transaction_id: str
    lot_id: str
    matched_quantity: float
    buy_unit_cost_krw: float
    sell_unit_price_krw: float
    allocated_fee_krw: float
    allocated_tax_krw: float
    realized_pnl_krw: float
    holding_days: int


def create_lot(execution: BuyExecution) -> PositionLot:
    return PositionLot(
        lot_id="lot-%s" % execution.transaction_id,
        buy_transaction_id=execution.transaction_id,
        security_id=execution.security_id,
        acquired_date=execution.acquired_date,
        original_quantity=execution.quantity,
        remaining_quantity=execution.quantity,
        unit_cost_krw=execution.unit_cost_krw,
    )


def match_sell_fifo(
    sell: SellExecution, lots: Iterable[PositionLot]
) -> Tuple[List[FifoMatch], float]:
    ordered_lots = sorted(
        [lot for lot in lots if lot.security_id == sell.security_id],
        key=lambda lot: (lot.acquired_date, lot.lot_id),
    )
    remaining_to_sell = sell.quantity
    matches: List[FifoMatch] = []

    if sell.quantity <= 0:
        raise ValueError("sell quantity must be positive")

    for lot in ordered_lots:
        if remaining_to_sell <= 0:
            break
        if lot.remaining_quantity <= 0:
            continue
        matched_quantity = min(lot.remaining_quantity, remaining_to_sell)
        fee_share = sell.fee_krw * (matched_quantity / sell.quantity)
        tax_share = sell.tax_krw * (matched_quantity / sell.quantity)
        gross_pnl = (sell.unit_price_krw - lot.unit_cost_krw) * matched_quantity
        realized_pnl = gross_pnl - fee_share - tax_share
        lot.remaining_quantity -= matched_quantity
        remaining_to_sell -= matched_quantity
        matches.append(
            FifoMatch(
                sell_transaction_id=sell.transaction_id,
                lot_id=lot.lot_id,
                matched_quantity=matched_quantity,
                buy_unit_cost_krw=lot.unit_cost_krw,
                sell_unit_price_krw=sell.unit_price_krw,
                allocated_fee_krw=round(fee_share, 2),
                allocated_tax_krw=round(tax_share, 2),
                realized_pnl_krw=round(realized_pnl, 2),
                holding_days=(sell.realized_date - lot.acquired_date).days,
            )
        )

    if remaining_to_sell > 0:
        raise ValueError("not enough remaining quantity to match sell execution")

    total_realized = round(sum(match.realized_pnl_krw for match in matches), 2)
    return matches, total_realized

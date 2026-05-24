from dataclasses import dataclass
from datetime import date
from typing import Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class BuyExecution:
    transaction_id: str
    security_id: str
    quantity: float
    unit_cost_krw: float
    acquired_date: date
    fee_krw: float = 0.0
    tax_krw: float = 0.0


@dataclass(frozen=True)
class ExecutionPosting:
    transaction_id: str
    account_id: str
    security_id: str
    side: str
    quantity: float
    unit_price_krw: float
    trade_date: date
    fee_krw: float = 0.0
    tax_krw: float = 0.0
    market: str = "KR"
    source_order_id: Optional[str] = None


@dataclass(frozen=True)
class TransactionLedgerEntry:
    transaction_id: str
    account_id: str
    security_id: str
    side: str
    quantity: float
    unit_price_krw: float
    gross_amount_krw: float
    fee_krw: float
    tax_krw: float
    net_cash_flow_krw: float
    trade_date: date
    source_order_id: Optional[str] = None


@dataclass(frozen=True)
class CashLedgerEntry:
    transaction_id: str
    account_id: str
    currency: str
    amount_krw: float
    entry_type: str
    entry_date: date


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


@dataclass(frozen=True)
class PostedExecutionResult:
    transaction_entry: TransactionLedgerEntry
    cash_entry: CashLedgerEntry
    created_lot: Optional[PositionLot] = None
    fifo_matches: Tuple[FifoMatch, ...] = ()
    realized_pnl_krw: float = 0.0


@dataclass(frozen=True)
class UnrealizedPnl:
    security_id: str
    quantity: float
    cost_basis_krw: float
    market_value_krw: float
    unrealized_pnl_krw: float
    unrealized_return_pct: float


@dataclass(frozen=True)
class ReconciliationInput:
    security_id: str
    broker_quantity: float
    internal_quantity: float
    broker_cash_krw: float
    internal_cash_krw: float


@dataclass(frozen=True)
class ReconciliationIssue:
    code: str
    message: str
    value: float
    tolerance: float


@dataclass(frozen=True)
class ReconciliationReport:
    status: str
    issues: Tuple[ReconciliationIssue, ...]


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


def create_transaction_ledger_entry(posting: ExecutionPosting) -> TransactionLedgerEntry:
    if posting.quantity <= 0:
        raise ValueError("quantity must be positive")
    if posting.unit_price_krw <= 0:
        raise ValueError("unit_price_krw must be positive")
    side = posting.side.strip().lower()
    if side not in {"buy", "sell"}:
        raise ValueError("side must be buy or sell")
    gross_amount = posting.quantity * posting.unit_price_krw
    if side == "buy":
        net_cash_flow = -(gross_amount + posting.fee_krw + posting.tax_krw)
    else:
        net_cash_flow = gross_amount - posting.fee_krw - posting.tax_krw
    return TransactionLedgerEntry(
        transaction_id=posting.transaction_id,
        account_id=posting.account_id,
        security_id=posting.security_id,
        side=side,
        quantity=posting.quantity,
        unit_price_krw=posting.unit_price_krw,
        gross_amount_krw=round(gross_amount, 2),
        fee_krw=round(posting.fee_krw, 2),
        tax_krw=round(posting.tax_krw, 2),
        net_cash_flow_krw=round(net_cash_flow, 2),
        trade_date=posting.trade_date,
        source_order_id=posting.source_order_id,
    )


def create_cash_ledger_entry(transaction: TransactionLedgerEntry) -> CashLedgerEntry:
    return CashLedgerEntry(
        transaction_id=transaction.transaction_id,
        account_id=transaction.account_id,
        currency="KRW",
        amount_krw=transaction.net_cash_flow_krw,
        entry_type="trade_settlement",
        entry_date=transaction.trade_date,
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


def calculate_unrealized_pnl(
    lots: Iterable[PositionLot],
    current_prices_krw: dict,
) -> List[UnrealizedPnl]:
    totals: dict = {}
    for lot in lots:
        if lot.remaining_quantity <= 0:
            continue
        if lot.security_id not in current_prices_krw:
            continue
        current_price = float(current_prices_krw[lot.security_id])
        cost_basis = lot.remaining_quantity * lot.unit_cost_krw
        market_value = lot.remaining_quantity * current_price
        quantity, cost, value = totals.get(lot.security_id, (0.0, 0.0, 0.0))
        totals[lot.security_id] = (
            quantity + lot.remaining_quantity,
            cost + cost_basis,
            value + market_value,
        )
    output: List[UnrealizedPnl] = []
    for security_id, (quantity, cost, value) in sorted(totals.items()):
        pnl = value - cost
        output.append(
            UnrealizedPnl(
                security_id=security_id,
                quantity=round(quantity, 8),
                cost_basis_krw=round(cost, 2),
                market_value_krw=round(value, 2),
                unrealized_pnl_krw=round(pnl, 2),
                unrealized_return_pct=0.0 if cost == 0 else round(pnl / cost, 6),
            )
        )
    return output


def post_execution_fifo(
    posting: ExecutionPosting, lots: Iterable[PositionLot]
) -> PostedExecutionResult:
    transaction = create_transaction_ledger_entry(posting)
    cash = create_cash_ledger_entry(transaction)

    if transaction.side == "buy":
        lot = create_lot(
            BuyExecution(
                transaction_id=transaction.transaction_id,
                security_id=transaction.security_id,
                quantity=transaction.quantity,
                unit_cost_krw=transaction.unit_price_krw,
                acquired_date=transaction.trade_date,
                fee_krw=transaction.fee_krw,
                tax_krw=transaction.tax_krw,
            )
        )
        return PostedExecutionResult(transaction, cash, created_lot=lot)

    matches, realized_pnl = match_sell_fifo(
        SellExecution(
            transaction_id=transaction.transaction_id,
            security_id=transaction.security_id,
            quantity=transaction.quantity,
            unit_price_krw=transaction.unit_price_krw,
            realized_date=transaction.trade_date,
            fee_krw=transaction.fee_krw,
            tax_krw=transaction.tax_krw,
        ),
        lots,
    )
    return PostedExecutionResult(
        transaction,
        cash,
        fifo_matches=tuple(matches),
        realized_pnl_krw=realized_pnl,
    )


def reconcile_position_and_cash(
    reconciliation: ReconciliationInput,
    quantity_tolerance: float = 0.000001,
    cash_tolerance_krw: float = 1.0,
) -> ReconciliationReport:
    issues: List[ReconciliationIssue] = []
    quantity_diff = reconciliation.internal_quantity - reconciliation.broker_quantity
    cash_diff = reconciliation.internal_cash_krw - reconciliation.broker_cash_krw
    if abs(quantity_diff) > quantity_tolerance:
        issues.append(
            ReconciliationIssue(
                "QUANTITY_MISMATCH",
                "internal position quantity differs from broker quantity",
                round(quantity_diff, 8),
                quantity_tolerance,
            )
        )
    if abs(cash_diff) > cash_tolerance_krw:
        issues.append(
            ReconciliationIssue(
                "CASH_MISMATCH",
                "internal cash balance differs from broker cash",
                round(cash_diff, 2),
                cash_tolerance_krw,
            )
        )
    return ReconciliationReport(
        status="match" if not issues else "mismatch",
        issues=tuple(issues),
    )

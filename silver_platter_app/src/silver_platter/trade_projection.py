from dataclasses import dataclass
from math import ceil
from typing import Dict, Iterable, List, Optional

from silver_platter.risk import BLOCK, WARNING, RiskDecision


@dataclass(frozen=True)
class TradeProjectionInput:
    side: str
    entry_price: float
    quantity: float
    fx_rate_krw: float
    order_amount_krw: float
    expected_slippage_krw: float
    annualized_volatility: float
    expected_return_annualized: float
    target_profit_pct: float
    avg_daily_turnover_20d_krw: Optional[float]


def build_trade_projection(
    projection_input: TradeProjectionInput,
    risk_decision: RiskDecision,
    horizon_days: Dict[str, int],
) -> Dict[str, object]:
    if projection_input.entry_price <= 0:
        raise ValueError("entry_price must be positive")
    if projection_input.quantity <= 0:
        raise ValueError("quantity must be positive")
    if projection_input.fx_rate_krw <= 0:
        raise ValueError("fx_rate_krw must be positive")

    normalized_side = projection_input.side.strip().lower()
    if normalized_side not in {"buy", "sell"}:
        raise ValueError("side must be buy or sell")

    slippage_per_unit = (
        projection_input.expected_slippage_krw
        / projection_input.quantity
        / projection_input.fx_rate_krw
    )
    direction = 1.0 if normalized_side == "buy" else -1.0
    break_even_price = projection_input.entry_price + direction * slippage_per_unit
    target_price = (
        projection_input.entry_price
        * (1.0 + direction * max(0.0, projection_input.target_profit_pct))
        + direction * slippage_per_unit
    )
    daily_return = projection_input.expected_return_annualized / 252.0

    horizon_projections = [
        _horizon_projection(
            label,
            days,
            projection_input,
            normalized_side,
            daily_return,
        )
        for label, days in horizon_days.items()
    ]
    best_projection = max(
        horizon_projections,
        key=lambda item: float(item["expected_profit_krw"]),
    )
    days_to_break_even = _estimated_days_to_price(
        projection_input.entry_price,
        break_even_price,
        normalized_side,
        daily_return,
    )
    days_to_target = _estimated_days_to_price(
        projection_input.entry_price,
        target_price,
        normalized_side,
        daily_return,
    )
    risk_score = _trade_risk_score(projection_input, risk_decision)
    guidance = _risk_guidance(risk_score, risk_decision.status)

    return {
        "side": normalized_side,
        "entry_price": round(projection_input.entry_price, 4),
        "break_even_price": round(max(0.0, break_even_price), 4),
        "target_profit_pct": round(max(0.0, projection_input.target_profit_pct) * 100.0, 4),
        "target_price": round(max(0.0, target_price), 4),
        "expected_return_annualized_pct": round(
            projection_input.expected_return_annualized * 100.0,
            4,
        ),
        "expected_profit_krw": round(float(best_projection["expected_profit_krw"]), 2),
        "expected_profit_pct": round(
            _pct_of_amount(
                float(best_projection["expected_profit_krw"]),
                projection_input.order_amount_krw,
            ),
            4,
        ),
        "best_horizon": best_projection["horizon"],
        "estimated_days_to_break_even": days_to_break_even,
        "estimated_days_to_target_profit": days_to_target,
        "estimated_holding_days": days_to_target or days_to_break_even,
        "risk_score": round(risk_score, 2),
        "risk_level": guidance["level"],
        "guidance": guidance,
        "horizon_projections": horizon_projections,
    }


def _horizon_projection(
    label: str,
    days: int,
    projection_input: TradeProjectionInput,
    side: str,
    daily_return: float,
) -> Dict[str, object]:
    expected_price = projection_input.entry_price * (1.0 + daily_return * days)
    if side == "buy":
        expected_profit = (
            (expected_price - projection_input.entry_price)
            * projection_input.quantity
            * projection_input.fx_rate_krw
            - projection_input.expected_slippage_krw
        )
    else:
        expected_profit = (
            (projection_input.entry_price - expected_price)
            * projection_input.quantity
            * projection_input.fx_rate_krw
            - projection_input.expected_slippage_krw
        )
    return {
        "horizon": label,
        "days": days,
        "expected_price": round(max(0.0, expected_price), 4),
        "expected_profit_krw": round(expected_profit, 2),
        "expected_profit_pct": round(
            _pct_of_amount(expected_profit, projection_input.order_amount_krw),
            4,
        ),
    }


def _estimated_days_to_price(
    entry_price: float,
    target_price: float,
    side: str,
    daily_return: float,
) -> Optional[int]:
    required_return = (target_price / entry_price) - 1.0
    if side == "sell":
        required_return = -required_return
        daily_return = -daily_return
    if required_return <= 0:
        return 0
    if daily_return <= 0:
        return None
    return max(1, int(ceil(required_return / daily_return)))


def _trade_risk_score(
    projection_input: TradeProjectionInput,
    risk_decision: RiskDecision,
) -> float:
    status_floor = 80.0 if risk_decision.status == BLOCK else 42.0 if risk_decision.status == WARNING else 0.0
    issue_component = sum(
        12.0 if issue.severity == BLOCK else 6.0
        for issue in risk_decision.issues
    )
    volatility_component = min(35.0, max(0.0, projection_input.annualized_volatility) * 100.0 * 0.8)
    liquidity_component = 20.0
    if projection_input.avg_daily_turnover_20d_krw and projection_input.avg_daily_turnover_20d_krw > 0:
        liquidity_ratio = projection_input.order_amount_krw / projection_input.avg_daily_turnover_20d_krw
        liquidity_component = min(25.0, liquidity_ratio / 0.05 * 25.0)
    return min(100.0, max(status_floor, issue_component + volatility_component + liquidity_component))


def _risk_guidance(risk_score: float, risk_status: str) -> Dict[str, object]:
    if risk_status == BLOCK or risk_score >= 80.0:
        return _guidance(
            "avoid",
            "critical",
            "Do not open a new buy until blocking risk inputs are resolved.",
            [
                "Cancel or postpone the order.",
                "Resolve blocked liquidity, size, or automation limits first.",
                "Re-run preview after reducing size or improving data quality.",
            ],
        )
    if risk_score >= 60.0:
        return _guidance(
            "reduce",
            "high",
            "Risk is high; use a smaller position or wait for a better entry.",
            [
                "Reduce order size and use a limit order.",
                "Split the entry across multiple sessions.",
                "Require stronger expected return before entering.",
            ],
        )
    if risk_score >= 35.0:
        return _guidance(
            "stage",
            "moderate",
            "Risk is moderate; staged entry and tighter review are appropriate.",
            [
                "Use a limit order near the planned entry price.",
                "Keep position size below the normal allocation.",
                "Review price and event risk again before adding.",
            ],
        )
    return _guidance(
        "proceed",
        "low",
        "Risk is low enough for the planned trade assumptions.",
        [
            "Proceed within the planned position size.",
            "Keep the target and break-even periods visible after entry.",
            "Re-check risk if price or volume moves sharply.",
        ],
    )


def _guidance(
    action: str,
    level: str,
    summary: str,
    actions: Iterable[str],
) -> Dict[str, object]:
    return {
        "action": action,
        "level": level,
        "summary": summary,
        "actions": list(actions),
    }


def _pct_of_amount(value: float, amount: float) -> float:
    if amount <= 0:
        return 0.0
    return value / amount * 100.0

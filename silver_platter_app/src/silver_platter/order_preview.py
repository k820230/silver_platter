from dataclasses import dataclass
from math import sqrt
from typing import Dict, Iterable, List, Optional

from silver_platter.risk import MvpRiskLimits, OrderRiskInput, evaluate_order_risk
from silver_platter.trade_projection import TradeProjectionInput, build_trade_projection


DEFAULT_HORIZON_DAYS = {
    "1d": 1,
    "1w": 5,
    "1m": 21,
    "3m": 63,
}


@dataclass(frozen=True)
class OrderPreviewInput:
    account_id: str
    security_id: str
    side: str
    order_type: str
    market: str
    current_price: float
    quantity: float
    avg_daily_turnover_20d_krw: Optional[float]
    volatility_annualized: float = 0.30
    is_auto_order: bool = False
    fx_rate_krw: float = 1.0
    horizons: Iterable[str] = ("1d", "1w", "1m", "3m")
    group_day_new_order_amount_krw: Optional[float] = None
    group_avg_daily_turnover_20d_krw: Optional[float] = None
    target_profit_pct: float = 0.02
    expected_return_annualized: float = 0.08


def _price_range(
    current_price: float, annualized_volatility: float, horizon_days: int
) -> Dict[str, float]:
    sigma = annualized_volatility * sqrt(horizon_days / 252.0)
    z = 1.65
    lower = current_price * (1 - z * sigma)
    upper = current_price * (1 + z * sigma)
    return {
        "lower": round(max(lower, 0.0), 4),
        "median": round(current_price, 4),
        "upper": round(max(upper, 0.0), 4),
    }


def create_order_preview(
    preview_input: OrderPreviewInput, limits: MvpRiskLimits = MvpRiskLimits()
) -> Dict[str, object]:
    horizons = list(preview_input.horizons)
    order_amount_krw = preview_input.current_price * preview_input.quantity
    order_amount_krw *= preview_input.fx_rate_krw

    risk_decision = evaluate_order_risk(
        OrderRiskInput(
            order_amount_krw=order_amount_krw,
            avg_daily_turnover_20d_krw=preview_input.avg_daily_turnover_20d_krw,
            market=preview_input.market,
            order_type=preview_input.order_type,
            is_auto_order=preview_input.is_auto_order,
            group_day_new_order_amount_krw=preview_input.group_day_new_order_amount_krw,
            group_avg_daily_turnover_20d_krw=preview_input.group_avg_daily_turnover_20d_krw,
        ),
        limits=limits,
    )
    expected_slippage_krw = (
        order_amount_krw * risk_decision.applied_slippage_bps / 10_000.0
    )

    ranges: List[Dict[str, object]] = []
    for horizon in horizons:
        horizon_days = DEFAULT_HORIZON_DAYS.get(horizon)
        if horizon_days is None:
            continue
        point = _price_range(
            preview_input.current_price,
            preview_input.volatility_annualized,
            horizon_days,
        )
        point["horizon"] = horizon
        point["expected_pnl_lower_krw"] = round(
            (point["lower"] - preview_input.current_price)
            * preview_input.quantity
            * preview_input.fx_rate_krw
            - expected_slippage_krw,
            2,
        )
        point["expected_pnl_upper_krw"] = round(
            (point["upper"] - preview_input.current_price)
            * preview_input.quantity
            * preview_input.fx_rate_krw
            - expected_slippage_krw,
            2,
        )
        ranges.append(point)

    investment_projection = build_trade_projection(
        TradeProjectionInput(
            side=preview_input.side,
            entry_price=preview_input.current_price,
            quantity=preview_input.quantity,
            fx_rate_krw=preview_input.fx_rate_krw,
            order_amount_krw=order_amount_krw,
            expected_slippage_krw=expected_slippage_krw,
            annualized_volatility=preview_input.volatility_annualized,
            expected_return_annualized=preview_input.expected_return_annualized,
            target_profit_pct=preview_input.target_profit_pct,
            avg_daily_turnover_20d_krw=preview_input.avg_daily_turnover_20d_krw,
        ),
        risk_decision,
        {
            horizon: days
            for horizon, days in DEFAULT_HORIZON_DAYS.items()
            if horizon in set(horizons)
        }
        or {"1m": DEFAULT_HORIZON_DAYS["1m"]},
    )

    return {
        "account_id": preview_input.account_id,
        "security_id": preview_input.security_id,
        "side": preview_input.side,
        "order_type": preview_input.order_type,
        "market": preview_input.market,
        "order_amount_krw": round(order_amount_krw, 2),
        "expected_slippage_krw": round(expected_slippage_krw, 2),
        "price_ranges": ranges,
        "investment_projection": investment_projection,
        "risk_check": risk_decision.as_dict(),
    }

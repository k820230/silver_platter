from dataclasses import dataclass
from math import log, sqrt
from typing import Iterable, List, Optional


@dataclass(frozen=True)
class VolatilityIndexResult:
    raw_volatility: float
    volatility_index: float
    quality_status: str


@dataclass(frozen=True)
class RiskIndexResult:
    risk_score: float
    risk_level: str
    quality_status: str


def ewma_annualized_volatility(
    close_prices: Iterable[float], lambda_value: float = 0.94, trading_days: int = 252
) -> Optional[float]:
    prices = [price for price in close_prices if price and price > 0]
    if len(prices) < 2:
        return None
    returns: List[float] = []
    for previous, current in zip(prices, prices[1:]):
        returns.append(log(current / previous))
    variance = returns[0] * returns[0]
    for value in returns[1:]:
        variance = lambda_value * variance + (1 - lambda_value) * value * value
    return sqrt(variance) * sqrt(trading_days)


def volatility_index_from_history(close_prices: Iterable[float]) -> VolatilityIndexResult:
    prices = list(close_prices)
    raw = ewma_annualized_volatility(prices)
    if raw is None:
        return VolatilityIndexResult(0.0, 0.0, "unavailable")
    # MVP normalization: 0% to 80% annualized volatility maps to 0~100.
    index = max(0.0, min(100.0, raw / 0.80 * 100.0))
    quality = "ok" if len(prices) >= 60 else "degraded"
    return VolatilityIndexResult(round(raw, 6), round(index, 4), quality)


def risk_level(score: float) -> str:
    if score >= 85:
        return "crisis"
    if score >= 70:
        return "danger"
    if score >= 40:
        return "caution"
    if score >= 20:
        return "watch"
    return "normal"


def component_risk_score(
    volatility_score: float,
    drawdown_score: float,
    liquidity_score: float,
    event_score: float,
    group_score: float,
    ml_score: float,
) -> RiskIndexResult:
    weighted = (
        0.25 * volatility_score
        + 0.20 * drawdown_score
        + 0.15 * liquidity_score
        + 0.20 * event_score
        + 0.10 * group_score
        + 0.10 * ml_score
    )
    score = max(0.0, min(100.0, weighted))
    return RiskIndexResult(round(score, 4), risk_level(score), "ok")

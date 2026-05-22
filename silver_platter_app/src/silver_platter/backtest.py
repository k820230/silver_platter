from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Callable, Dict, Iterable, List, Optional

from silver_platter.data_quality import PriceBarInput
from silver_platter.simulation import SimulationEngine, SimulatedExecutionResult, VirtualAccount


@dataclass(frozen=True)
class StrategyOrderCandidate:
    security_id: str
    side: str
    market: str
    order_type: str
    price: float
    quantity: float
    decision_at: datetime
    avg_daily_turnover_20d_krw: float


@dataclass(frozen=True)
class BacktestRunConfig:
    run_id: str
    strategy_id: str
    from_date: date
    to_date: date
    initial_cash_krw: float = 100_000_000.0
    market_scope: str = "BOTH"


@dataclass(frozen=True)
class BacktestOrderEvent:
    candidate: StrategyOrderCandidate
    accepted: bool
    reason: str
    realized_pnl_krw: float = 0.0


@dataclass(frozen=True)
class BacktestResult:
    run_id: str
    status: str
    order_events: List[BacktestOrderEvent]
    ending_cash_krw: float
    realized_pnl_krw: float
    blocked_order_count: int
    lookahead_violation_count: int
    metrics: Dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ScenarioShock:
    scenario_id: str
    name: str
    price_shock_pct: float = 0.0
    fx_shock_pct: float = 0.0
    liquidity_multiplier: float = 1.0


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    shocked_price: float
    shocked_fx_rate: float
    shocked_turnover_krw: float


StrategyFn = Callable[[PriceBarInput], Optional[StrategyOrderCandidate]]


def assert_no_lookahead(bars: Iterable[PriceBarInput], decision_at: datetime) -> int:
    violations = 0
    for bar in bars:
        if bar.available_to_model_at is None or bar.available_to_model_at > decision_at:
            violations += 1
    return violations


def run_backtest(
    config: BacktestRunConfig,
    bars: Iterable[PriceBarInput],
    strategy: StrategyFn,
) -> BacktestResult:
    sorted_bars = sorted(list(bars), key=lambda item: item.bar_ts)
    account = VirtualAccount(config.run_id, cash_krw=config.initial_cash_krw)
    engine = SimulationEngine(account)
    events: List[BacktestOrderEvent] = []
    lookahead_violations = 0

    for bar in sorted_bars:
        if not (config.from_date <= bar.bar_ts.date() <= config.to_date):
            continue
        if bar.available_to_model_at is None or bar.available_to_model_at > bar.bar_ts:
            lookahead_violations += 1
            continue
        candidate = strategy(bar)
        if candidate is None:
            continue
        lookahead_violations += assert_no_lookahead([bar], candidate.decision_at)
        if lookahead_violations:
            events.append(BacktestOrderEvent(candidate, False, "lookahead_violation"))
            continue
        result: SimulatedExecutionResult = engine.execute(
            security_id=candidate.security_id,
            side=candidate.side,
            market=candidate.market,
            order_type=candidate.order_type,
            price=candidate.price,
            quantity=candidate.quantity,
            avg_daily_turnover_20d_krw=candidate.avg_daily_turnover_20d_krw,
            trade_date=candidate.decision_at.date(),
        )
        events.append(
            BacktestOrderEvent(
                candidate=candidate,
                accepted=result.accepted,
                reason=result.reason,
                realized_pnl_krw=result.realized_pnl_krw,
            )
        )

    blocked = len([event for event in events if not event.accepted])
    invested_basis = config.initial_cash_krw if config.initial_cash_krw else 1.0
    return BacktestResult(
        run_id=config.run_id,
        status="completed",
        order_events=events,
        ending_cash_krw=round(account.cash_krw, 2),
        realized_pnl_krw=round(account.realized_pnl_krw, 2),
        blocked_order_count=blocked,
        lookahead_violation_count=lookahead_violations,
        metrics={
            "realized_return_pct": round(account.realized_pnl_krw / invested_basis, 8),
            "order_count": float(len(events)),
            "blocked_order_count": float(blocked),
        },
    )


def apply_scenario_shock(
    current_price: float,
    fx_rate: float,
    avg_daily_turnover_20d_krw: float,
    shock: ScenarioShock,
) -> ScenarioResult:
    if shock.liquidity_multiplier <= 0:
        raise ValueError("liquidity_multiplier must be positive")
    return ScenarioResult(
        scenario_id=shock.scenario_id,
        shocked_price=round(current_price * (1.0 + shock.price_shock_pct), 4),
        shocked_fx_rate=round(fx_rate * (1.0 + shock.fx_shock_pct), 6),
        shocked_turnover_krw=round(
            avg_daily_turnover_20d_krw * shock.liquidity_multiplier,
            2,
        ),
    )

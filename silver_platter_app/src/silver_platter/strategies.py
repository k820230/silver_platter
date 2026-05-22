from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from silver_platter.backtest import StrategyFn, StrategyOrderCandidate
from silver_platter.data_quality import PriceBarInput


@dataclass(frozen=True)
class StrategyContext:
    strategy_id: str
    security_id: str
    market: str
    side: str
    order_type: str
    quantity: float
    avg_daily_turnover_20d_krw: float
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StrategyPlugin:
    plugin_id: str
    name: str
    description: str
    factory: Callable[[StrategyContext], StrategyFn]

    def as_dict(self) -> dict:
        return {
            "plugin_id": self.plugin_id,
            "name": self.name,
            "description": self.description,
        }


class StrategyRegistry:
    def __init__(self, plugins: Optional[List[StrategyPlugin]] = None) -> None:
        self._plugins: Dict[str, StrategyPlugin] = {}
        for plugin in plugins or []:
            self.register(plugin)

    def register(self, plugin: StrategyPlugin) -> None:
        if plugin.plugin_id in self._plugins:
            raise ValueError("duplicate strategy plugin: %s" % plugin.plugin_id)
        self._plugins[plugin.plugin_id] = plugin

    def get(self, plugin_id: str) -> StrategyPlugin:
        try:
            return self._plugins[plugin_id]
        except KeyError as exc:
            raise ValueError("unknown strategy plugin: %s" % plugin_id) from exc

    def build(self, plugin_id: str, context: StrategyContext) -> StrategyFn:
        return self.get(plugin_id).factory(context)

    def list_plugins(self) -> List[StrategyPlugin]:
        return [self._plugins[key] for key in sorted(self._plugins)]


def _order_candidate(context: StrategyContext, bar: PriceBarInput) -> StrategyOrderCandidate:
    return StrategyOrderCandidate(
        security_id=context.security_id,
        side=context.side,
        market=context.market,
        order_type=context.order_type,
        price=float(bar.close_price or 0.0),
        quantity=context.quantity,
        decision_at=bar.bar_ts,
        avg_daily_turnover_20d_krw=context.avg_daily_turnover_20d_krw,
    )


def fixed_close_strategy(context: StrategyContext) -> StrategyFn:
    def strategy(bar: PriceBarInput) -> StrategyOrderCandidate:
        return _order_candidate(context, bar)

    return strategy


def momentum_threshold_strategy(context: StrategyContext) -> StrategyFn:
    min_return_pct = float(context.parameters.get("min_return_pct", 0.01))
    previous_close: Optional[float] = None

    def strategy(bar: PriceBarInput) -> Optional[StrategyOrderCandidate]:
        nonlocal previous_close
        close_price = float(bar.close_price or 0.0)
        if previous_close is None or previous_close <= 0 or close_price <= 0:
            previous_close = close_price
            return None
        return_pct = (close_price / previous_close) - 1.0
        previous_close = close_price
        if return_pct < min_return_pct:
            return None
        return _order_candidate(context, bar)

    return strategy


DEFAULT_STRATEGY_REGISTRY = StrategyRegistry(
    [
        StrategyPlugin(
            plugin_id="fixed-close",
            name="Fixed close replay",
            description="Submit a fixed-size order at each eligible bar close.",
            factory=fixed_close_strategy,
        ),
        StrategyPlugin(
            plugin_id="momentum-threshold",
            name="Momentum threshold replay",
            description="Submit only after close-to-close return exceeds min_return_pct.",
            factory=momentum_threshold_strategy,
        ),
    ]
)

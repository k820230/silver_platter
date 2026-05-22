from datetime import datetime
from unittest import TestCase

from silver_platter.providers import sample_bar
from silver_platter.strategies import DEFAULT_STRATEGY_REGISTRY, StrategyContext


class StrategyPluginTests(TestCase):
    def test_default_registry_lists_builtin_plugins(self):
        plugins = DEFAULT_STRATEGY_REGISTRY.list_plugins()

        self.assertEqual(["fixed-close", "momentum-threshold"], [plugin.plugin_id for plugin in plugins])

    def test_fixed_close_strategy_emits_order_for_each_bar(self):
        strategy = DEFAULT_STRATEGY_REGISTRY.build(
            "fixed-close",
            StrategyContext(
                strategy_id="s1",
                security_id="AAPL",
                market="US",
                side="buy",
                order_type="limit",
                quantity=3,
                avg_daily_turnover_20d_krw=1_000_000_000,
            ),
        )

        candidate = strategy(sample_bar("AAPL", datetime(2026, 5, 22, 9, 0, 0), 200.0))

        self.assertIsNotNone(candidate)
        self.assertEqual("AAPL", candidate.security_id)
        self.assertEqual(3, candidate.quantity)
        self.assertEqual(200.0, candidate.price)

    def test_momentum_threshold_strategy_waits_for_required_return(self):
        strategy = DEFAULT_STRATEGY_REGISTRY.build(
            "momentum-threshold",
            StrategyContext(
                strategy_id="s1",
                security_id="AAPL",
                market="US",
                side="buy",
                order_type="limit",
                quantity=1,
                avg_daily_turnover_20d_krw=1_000_000_000,
                parameters={"min_return_pct": 0.01},
            ),
        )

        first = strategy(sample_bar("AAPL", datetime(2026, 5, 22, 9, 0, 0), 100.0))
        second = strategy(sample_bar("AAPL", datetime(2026, 5, 23, 9, 0, 0), 100.5))
        third = strategy(sample_bar("AAPL", datetime(2026, 5, 24, 9, 0, 0), 102.0))

        self.assertIsNone(first)
        self.assertIsNone(second)
        self.assertIsNotNone(third)
        self.assertEqual(102.0, third.price)

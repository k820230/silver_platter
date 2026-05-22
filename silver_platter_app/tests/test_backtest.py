from datetime import date, datetime
from unittest import TestCase

from silver_platter.backtest import (
    BacktestRunConfig,
    ScenarioShock,
    StrategyOrderCandidate,
    apply_scenario_shock,
    assert_no_lookahead,
    run_backtest,
)
from silver_platter.data_quality import PriceBarInput


class BacktestTests(TestCase):
    def test_lookahead_violation_counts_unavailable_bar(self):
        violations = assert_no_lookahead(
            [
                PriceBarInput(
                    "AAPL",
                    datetime(2026, 5, 22, 9, 0, 0),
                    200,
                    1000,
                    200000,
                    datetime(2026, 5, 22, 9, 1, 0),
                )
            ],
            datetime(2026, 5, 22, 9, 0, 0),
        )

        self.assertEqual(1, violations)

    def test_run_backtest_uses_simulation_risk_gate(self):
        def strategy(bar):
            return StrategyOrderCandidate(
                security_id=bar.security_id,
                side="buy",
                market="US",
                order_type="limit",
                price=bar.close_price,
                quantity=10,
                decision_at=bar.bar_ts,
                avg_daily_turnover_20d_krw=100_000_000,
            )

        result = run_backtest(
            BacktestRunConfig("bt-1", "s1", date(2026, 5, 22), date(2026, 5, 22)),
            [
                PriceBarInput(
                    "AAPL",
                    datetime(2026, 5, 22, 9, 0, 0),
                    20000,
                    1000,
                    20_000_000,
                    datetime(2026, 5, 22, 9, 0, 0),
                )
            ],
            strategy,
        )

        self.assertEqual("completed", result.status)
        self.assertEqual(1, len(result.order_events))
        self.assertTrue(result.order_events[0].accepted)

    def test_scenario_shock_adjusts_price_fx_and_liquidity(self):
        result = apply_scenario_shock(
            100,
            1300,
            1_000_000_000,
            ScenarioShock("s1", "market drop", price_shock_pct=-0.10, fx_shock_pct=0.08, liquidity_multiplier=0.5),
        )

        self.assertEqual(90, result.shocked_price)
        self.assertEqual(1404, result.shocked_fx_rate)
        self.assertEqual(500_000_000, result.shocked_turnover_krw)

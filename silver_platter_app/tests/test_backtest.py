from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from silver_platter.backtest import (
    BacktestRunConfig,
    BacktestResult,
    ScenarioShock,
    StrategyOrderCandidate,
    apply_scenario_shock,
    assert_no_lookahead,
    build_paper_replay_evidence,
    run_backtest,
)
from silver_platter.data_quality import PriceBarInput
from silver_platter.exports import export_price_bars_partitioned, load_price_bars_from_exported_files


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
        self.assertEqual(1.0, result.metrics["replay_day_count"])
        self.assertEqual(1.0, result.metrics["accepted_order_count"])

    def test_build_paper_replay_evidence_passes_clean_simulation(self):
        result = BacktestResult(
            run_id="bt-paper",
            status="completed",
            order_events=[],
            ending_cash_krw=100_000_000,
            realized_pnl_krw=0,
            blocked_order_count=0,
            lookahead_violation_count=0,
            metrics={
                "replay_day_count": 10.0,
                "order_count": 3.0,
                "accepted_order_count": 3.0,
            },
        )

        evidence = build_paper_replay_evidence(
            result,
            required_min_days=10,
            generated_at=datetime(2026, 5, 22, 9, 0, 0),
        )

        self.assertEqual("pass", evidence.status)
        self.assertFalse(evidence.broker_send_attempted)
        self.assertEqual(10, evidence.as_dict()["replay_day_count"])
        self.assertEqual("broker_send_forbidden", evidence.evidence["simulation_broker_send_policy"])

    def test_build_paper_replay_evidence_fails_broker_send_attempt(self):
        result = BacktestResult(
            run_id="bt-paper",
            status="completed",
            order_events=[],
            ending_cash_krw=100_000_000,
            realized_pnl_krw=0,
            blocked_order_count=0,
            lookahead_violation_count=0,
            metrics={"replay_day_count": 10.0},
        )

        evidence = build_paper_replay_evidence(result, broker_send_attempted=True)

        self.assertEqual("fail", evidence.status)
        self.assertEqual("broker_send_attempted", evidence.evidence["failure_reason"])

    def test_run_backtest_from_exported_snapshot_files(self):
        bars = [
            PriceBarInput(
                "AAPL",
                datetime(2026, 5, 22, 9, 0, 0),
                20_000,
                1000,
                20_000_000,
                datetime(2026, 5, 22, 9, 0, 0),
            ),
            PriceBarInput(
                "AAPL",
                datetime(2026, 5, 23, 9, 0, 0),
                21_000,
                1000,
                21_000_000,
                datetime(2026, 5, 23, 9, 0, 0),
            ),
        ]

        def strategy(bar):
            return StrategyOrderCandidate(
                security_id=bar.security_id,
                side="buy",
                market="US",
                order_type="limit",
                price=bar.close_price,
                quantity=1,
                decision_at=bar.bar_ts,
                avg_daily_turnover_20d_krw=100_000_000,
            )

        with TemporaryDirectory() as tmp:
            exported = export_price_bars_partitioned(
                bars,
                Path(tmp),
                provider_code="free",
                prefer_parquet=False,
            )
            loaded = load_price_bars_from_exported_files(exported.files)

        result = run_backtest(
            BacktestRunConfig("bt-snapshot", "s1", date(2026, 5, 22), date(2026, 5, 23)),
            loaded,
            strategy,
        )

        self.assertEqual("completed", result.status)
        self.assertEqual(2, len(result.order_events))
        self.assertEqual(2.0, result.metrics["replay_day_count"])

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

import unittest

from silver_platter.risk import BLOCK, WARNING, OrderRiskInput, evaluate_order_risk


class RiskEngineTest(unittest.TestCase):
    def test_blocks_order_under_minimum_amount(self):
        decision = evaluate_order_risk(
            OrderRiskInput(
                order_amount_krw=50_000,
                avg_daily_turnover_20d_krw=10_000_000_000,
                market="KR",
                order_type="limit",
            )
        )
        self.assertEqual(decision.status, BLOCK)
        self.assertIn("AMOUNT_BELOW_MIN", [issue.code for issue in decision.issues])

    def test_blocks_liquidity_above_five_percent_adv20(self):
        decision = evaluate_order_risk(
            OrderRiskInput(
                order_amount_krw=600_000_000,
                avg_daily_turnover_20d_krw=10_000_000_000,
                market="KR",
                order_type="market",
            )
        )
        self.assertEqual(decision.status, BLOCK)
        self.assertIn(
            "LIQUIDITY_LIMIT_EXCEEDED", [issue.code for issue in decision.issues]
        )

    def test_low_liquidity_applies_three_times_slippage(self):
        decision = evaluate_order_risk(
            OrderRiskInput(
                order_amount_krw=1_000_000,
                avg_daily_turnover_20d_krw=500_000_000,
                market="KR",
                order_type="market",
            )
        )
        self.assertEqual(decision.status, WARNING)
        self.assertEqual(decision.low_liquidity_multiplier, 3.0)
        self.assertEqual(decision.applied_slippage_bps, 30.0)

    def test_blocks_group_liquidity_limit(self):
        decision = evaluate_order_risk(
            OrderRiskInput(
                order_amount_krw=1_000_000,
                avg_daily_turnover_20d_krw=10_000_000_000,
                market="US",
                order_type="limit",
                group_day_new_order_amount_krw=600_000_000,
                group_avg_daily_turnover_20d_krw=10_000_000_000,
            )
        )
        self.assertEqual(decision.status, BLOCK)
        self.assertIn(
            "GROUP_LIQUIDITY_LIMIT_EXCEEDED",
            [issue.code for issue in decision.issues],
        )


if __name__ == "__main__":
    unittest.main()

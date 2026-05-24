import unittest

from silver_platter.order_preview import OrderPreviewInput, create_order_preview


class OrderPreviewTest(unittest.TestCase):
    def test_preview_contains_default_horizons_and_risk(self):
        preview = create_order_preview(
            OrderPreviewInput(
                account_id="sim-1",
                security_id="KR-005930",
                side="buy",
                order_type="limit",
                market="KR",
                current_price=70_000,
                quantity=10,
                avg_daily_turnover_20d_krw=100_000_000_000,
            )
        )
        self.assertEqual(preview["order_amount_krw"], 700_000)
        self.assertEqual(preview["risk_check"]["status"], "pass")
        self.assertEqual(
            [point["horizon"] for point in preview["price_ranges"]],
            ["1d", "1w", "1m", "3m"],
        )
        projection = preview["investment_projection"]
        self.assertEqual("buy", projection["side"])
        self.assertGreater(projection["break_even_price"], 70_000)
        self.assertGreater(projection["target_price"], projection["break_even_price"])
        self.assertIsNotNone(projection["estimated_days_to_break_even"])
        self.assertIsNotNone(projection["estimated_days_to_target_profit"])
        self.assertIn(
            projection["guidance"]["action"],
            {"proceed", "stage", "reduce", "avoid"},
        )

    def test_preview_blocks_missing_liquidity(self):
        preview = create_order_preview(
            OrderPreviewInput(
                account_id="sim-1",
                security_id="US-XYZ",
                side="buy",
                order_type="market",
                market="US",
                current_price=100,
                quantity=10,
                avg_daily_turnover_20d_krw=None,
                fx_rate_krw=1300,
            )
        )
        self.assertEqual(preview["risk_check"]["status"], "block")
        self.assertEqual("avoid", preview["investment_projection"]["guidance"]["action"])

    def test_preview_uses_target_profit_for_investment_period(self):
        preview = create_order_preview(
            OrderPreviewInput(
                account_id="sim-1",
                security_id="KR-005930",
                side="buy",
                order_type="limit",
                market="KR",
                current_price=100,
                quantity=100,
                avg_daily_turnover_20d_krw=10_000_000_000,
                target_profit_pct=0.04,
                expected_return_annualized=0.20,
            )
        )

        projection = preview["investment_projection"]
        self.assertEqual(4.0, projection["target_profit_pct"])
        self.assertGreaterEqual(projection["estimated_days_to_target_profit"], 50)
        self.assertEqual("3m", projection["best_horizon"])


if __name__ == "__main__":
    unittest.main()

import unittest

from silver_platter.indices import component_risk_score, ewma_annualized_volatility


class IndexTest(unittest.TestCase):
    def test_ewma_volatility_is_positive_for_moving_prices(self):
        value = ewma_annualized_volatility([100, 101, 99, 102, 98, 103])
        self.assertIsNotNone(value)
        self.assertGreater(value, 0)

    def test_component_risk_score_uses_mvp_weights(self):
        result = component_risk_score(
            volatility_score=80,
            drawdown_score=60,
            liquidity_score=40,
            event_score=100,
            group_score=50,
            ml_score=30,
        )
        self.assertEqual(result.risk_score, 66.0)
        self.assertEqual(result.risk_level, "caution")


if __name__ == "__main__":
    unittest.main()

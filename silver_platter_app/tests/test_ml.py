from datetime import datetime
from unittest import TestCase

from silver_platter.ml import FeatureSnapshot, ModelRegistry, predict_many


class MlTests(TestCase):
    def test_predicts_requested_security_metrics(self):
        registry = ModelRegistry()
        predictions = predict_many(
            registry,
            [
                FeatureSnapshot(
                    security_id="AAPL",
                    as_of=datetime(2026, 5, 22, 9, 0, 0),
                    last_price=200.0,
                    avg_volume_20d=50_000_000,
                    annualized_volatility=0.30,
                    risk_score=35.0,
                )
            ],
        )

        self.assertEqual(4, len(predictions["AAPL"]))
        self.assertEqual("1d", predictions["AAPL"][0].horizon)
        self.assertLess(predictions["AAPL"][0].price_lower, 200.0)
        self.assertGreater(predictions["AAPL"][0].price_upper, 200.0)

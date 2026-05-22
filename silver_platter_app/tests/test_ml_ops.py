from datetime import datetime
from unittest import TestCase

from silver_platter.ml import FeatureSnapshot
from silver_platter.ml_ops import (
    PredictionActual,
    WatchlistRegistry,
    attach_prediction_actual,
    create_prediction_job,
    run_prediction_job,
    summarize_prediction_errors,
)


class MlOpsTests(TestCase):
    def test_watchlist_add_remove_and_list_active(self):
        registry = WatchlistRegistry()
        registry.add("u1", "AAPL")
        registry.add("u1", "MSFT")
        registry.remove("u1", "AAPL")

        active = registry.list_active("u1")
        self.assertEqual(["MSFT"], [item.security_id for item in active])

    def test_prediction_job_actual_and_error_summary(self):
        job = create_prediction_job("job-1", "AAPL", ["1d", "bad"])
        predictions = run_prediction_job(
            job,
            FeatureSnapshot(
                security_id="AAPL",
                as_of=datetime(2026, 5, 22, 9, 0, 0),
                last_price=200.0,
                avg_volume_20d=50_000_000,
                annualized_volatility=0.30,
                risk_score=30.0,
            ),
        )
        completed = attach_prediction_actual(
            predictions[0],
            PredictionActual(
                prediction_id=predictions[0].prediction_id,
                actual_price=203.0,
                observed_at=predictions[0].target_at,
            ),
        )
        summary = summarize_prediction_errors([completed], "AAPL")

        self.assertEqual(1, len(predictions))
        self.assertEqual(1, summary.sample_count)
        self.assertGreater(summary.mean_absolute_error, 0)

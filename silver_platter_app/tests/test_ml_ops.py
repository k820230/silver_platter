from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from silver_platter.data_quality import PriceBarInput
from silver_platter.ml import FeatureSnapshot
from silver_platter.ml_ops import (
    InMemoryPredictionJobQueue,
    PredictionActual,
    WatchlistRegistry,
    attach_prediction_actual,
    create_prediction_job,
    enqueue_prediction_job,
    match_due_prediction_actuals,
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

    def test_watchlist_registry_json_round_trip_preserves_active_state(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "watchlist.json"
            registry = WatchlistRegistry()
            registry.add("u1", "AAPL", note="core")
            registry.add("u1", "MSFT")
            registry.remove("u1", "MSFT")

            registry.save_json(path)
            loaded = WatchlistRegistry.load_json(path)

        self.assertEqual(["AAPL"], [item.security_id for item in loaded.list_active("u1")])
        self.assertEqual("core", loaded.items[("u1", "AAPL")].note)
        self.assertFalse(loaded.items[("u1", "MSFT")].is_active)

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

    def test_in_memory_prediction_job_queue_runs_fifo(self):
        queue = InMemoryPredictionJobQueue()
        job = create_prediction_job("job-queue", "AAPL", ["1d"])
        snapshot = FeatureSnapshot(
            security_id="AAPL",
            as_of=datetime(2026, 5, 22, 9, 0, 0),
            last_price=200.0,
            avg_volume_20d=50_000_000,
            annualized_volatility=0.30,
            risk_score=30.0,
        )

        queued = queue.enqueue(job, snapshot)
        predictions = queue.run_next()

        self.assertEqual("job-queue", queued.job.job_id)
        self.assertEqual(0, queue.pending_count())
        self.assertEqual("job-queue-1d", predictions[0].prediction_id)
        self.assertIsNone(queue.run_next())

    def test_enqueue_prediction_job_uses_queue_enqueue_boundary(self):
        class FakeQueue:
            def __init__(self):
                self.calls = []

            def enqueue(self, fn, *args):
                self.calls.append((fn, args))
                return "queued"

        queue = FakeQueue()
        job = create_prediction_job("job-rq", "AAPL", ["1d"])
        snapshot = FeatureSnapshot(
            security_id="AAPL",
            as_of=datetime(2026, 5, 22, 9, 0, 0),
            last_price=200.0,
            avg_volume_20d=50_000_000,
            annualized_volatility=0.30,
            risk_score=30.0,
        )

        result = enqueue_prediction_job(queue, job, snapshot)

        self.assertEqual("queued", result)
        self.assertIs(run_prediction_job, queue.calls[0][0])
        self.assertEqual((job, snapshot), queue.calls[0][1])

    def test_match_due_prediction_actuals_uses_first_available_target_bar(self):
        job = create_prediction_job("job-2", "AAPL", ["1d"])
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
        matched = match_due_prediction_actuals(
            predictions,
            [
                PriceBarInput(
                    security_id="AAPL",
                    bar_ts=datetime(2026, 5, 24, 15, 0, 0),
                    close_price=204.0,
                    volume=1_000_000,
                    turnover_krw=10_000_000_000,
                    available_to_model_at=datetime(2026, 5, 24, 16, 0, 0),
                ),
                PriceBarInput(
                    security_id="AAPL",
                    bar_ts=datetime(2026, 5, 23, 15, 0, 0),
                    close_price=203.0,
                    volume=1_000_000,
                    turnover_krw=10_000_000_000,
                    available_to_model_at=datetime(2026, 5, 23, 16, 0, 0),
                ),
            ],
            observed_at=datetime(2026, 5, 24, 9, 0, 0),
        )

        self.assertEqual(203.0, matched[0].actual_price)
        self.assertIsNotNone(matched[0].absolute_error)

    def test_match_due_prediction_actuals_ignores_not_due_or_unavailable_bars(self):
        job = create_prediction_job("job-3", "AAPL", ["1d"])
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

        not_due = match_due_prediction_actuals(
            predictions,
            [
                PriceBarInput(
                    security_id="AAPL",
                    bar_ts=datetime(2026, 5, 23, 15, 0, 0),
                    close_price=203.0,
                    volume=1_000_000,
                    turnover_krw=10_000_000_000,
                    available_to_model_at=datetime(2026, 5, 23, 16, 0, 0),
                ),
            ],
            observed_at=datetime(2026, 5, 22, 12, 0, 0),
        )
        unavailable = match_due_prediction_actuals(
            predictions,
            [
                PriceBarInput(
                    security_id="AAPL",
                    bar_ts=datetime(2026, 5, 23, 15, 0, 0),
                    close_price=203.0,
                    volume=1_000_000,
                    turnover_krw=10_000_000_000,
                    available_to_model_at=datetime(2026, 5, 24, 16, 0, 0),
                ),
            ],
            observed_at=datetime(2026, 5, 23, 9, 0, 0),
        )

        self.assertIsNone(not_due[0].actual_price)
        self.assertIsNone(unavailable[0].actual_price)

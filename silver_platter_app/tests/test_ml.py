from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from silver_platter.ml import (
    FeatureSnapshot,
    ModelRegistry,
    ModelSpec,
    load_model_registry_artifact,
    predict_many,
    save_model_registry_artifact,
)


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

    def test_model_registry_artifact_round_trip(self):
        with TemporaryDirectory() as tmp:
            registry = ModelRegistry()
            registry.register(
                ModelSpec(
                    security_id="AAPL",
                    model_id="aapl-model",
                    version="2026.05",
                    horizons=("1d", "1w"),
                    fine_tuned=False,
                    status="candidate",
                )
            )

            path = save_model_registry_artifact(registry, Path(tmp))
            loaded = load_model_registry_artifact(path)

        spec = loaded.active_for("AAPL")
        self.assertEqual("aapl-model", spec.model_id)
        self.assertEqual("2026.05", spec.version)
        self.assertEqual(("1d", "1w"), spec.horizons)
        self.assertFalse(spec.fine_tuned)
        self.assertEqual("candidate", spec.status)

    def test_missing_model_registry_artifact_loads_empty_registry(self):
        with TemporaryDirectory() as tmp:
            loaded = load_model_registry_artifact(Path(tmp) / "missing.json")

        self.assertEqual({}, loaded.models)

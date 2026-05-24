from dataclasses import dataclass, field
from datetime import datetime
import json
from math import sqrt
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


HORIZON_DAYS = {
    "1d": 1,
    "1w": 5,
    "1m": 21,
    "3m": 63,
}


@dataclass(frozen=True)
class ModelSpec:
    security_id: str
    model_id: str
    version: str
    horizons: Tuple[str, ...] = ("1d", "1w", "1m", "3m")
    fine_tuned: bool = True
    fine_tune_reason: str = "security-specific baseline enabled"
    feature_set_version: str = "baseline-price-volume-risk-v1"
    status: str = "active"


@dataclass(frozen=True)
class FeatureSnapshot:
    security_id: str
    as_of: datetime
    last_price: float
    avg_volume_20d: float
    annualized_volatility: float
    risk_score: float
    drift_per_day: float = 0.0


@dataclass(frozen=True)
class PredictionInterval:
    horizon: str
    price_lower: float
    price_mid: float
    price_upper: float
    volume_lower: float
    volume_mid: float
    volume_upper: float
    volatility_lower: float
    volatility_mid: float
    volatility_upper: float
    risk_score: float


@dataclass
class ModelRegistry:
    models: Dict[str, ModelSpec] = field(default_factory=dict)

    def register(self, spec: ModelSpec) -> None:
        self.models[spec.security_id] = spec

    def active_for(self, security_id: str) -> ModelSpec:
        if security_id in self.models:
            return self.models[security_id]
        spec = ModelSpec(
            security_id=security_id,
            model_id="baseline-%s" % security_id.lower(),
            version="0.1.0",
        )
        self.register(spec)
        return spec


def _model_spec_to_dict(spec: ModelSpec) -> dict:
    return {
        "security_id": spec.security_id,
        "model_id": spec.model_id,
        "version": spec.version,
        "horizons": list(spec.horizons),
        "fine_tuned": spec.fine_tuned,
        "fine_tune_reason": spec.fine_tune_reason,
        "feature_set_version": spec.feature_set_version,
        "status": spec.status,
    }


def _model_spec_from_dict(payload: dict) -> ModelSpec:
    return ModelSpec(
        security_id=str(payload["security_id"]),
        model_id=str(payload["model_id"]),
        version=str(payload["version"]),
        horizons=tuple(payload.get("horizons", ("1d", "1w", "1m", "3m"))),
        fine_tuned=bool(payload.get("fine_tuned", True)),
        fine_tune_reason=str(
            payload.get("fine_tune_reason", "security-specific baseline enabled")
        ),
        feature_set_version=str(
            payload.get("feature_set_version", "baseline-price-volume-risk-v1")
        ),
        status=str(payload.get("status", "active")),
    )


def save_model_registry_artifact(
    registry: ModelRegistry,
    artifact_dir: Path,
    filename: str = "model_registry.json",
) -> Path:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    path = artifact_dir / filename
    payload = {
        "models": [
            _model_spec_to_dict(registry.models[key])
            for key in sorted(registry.models.keys())
        ]
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    return path


def load_model_registry_artifact(path: Path) -> ModelRegistry:
    if not path.exists():
        return ModelRegistry()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
        raise ValueError("model registry artifact must contain a models list")
    registry = ModelRegistry()
    for item in payload["models"]:
        if not isinstance(item, dict):
            raise ValueError("model registry artifact entry must be an object")
        registry.register(_model_spec_from_dict(item))
    return registry


def predict_security_metrics(
    model: ModelSpec, snapshot: FeatureSnapshot
) -> List[PredictionInterval]:
    if snapshot.last_price <= 0:
        raise ValueError("last_price must be positive")
    if snapshot.avg_volume_20d < 0:
        raise ValueError("avg_volume_20d must be zero or positive")
    if snapshot.annualized_volatility < 0:
        raise ValueError("annualized_volatility must be zero or positive")

    predictions: List[PredictionInterval] = []
    for horizon in model.horizons:
        days = HORIZON_DAYS.get(horizon)
        if days is None:
            continue
        time_scale = sqrt(days / 252.0)
        expected_return = snapshot.drift_per_day * days
        sigma = snapshot.annualized_volatility * time_scale
        price_mid = snapshot.last_price * (1.0 + expected_return)
        price_lower = snapshot.last_price * max(0.0, 1.0 + expected_return - 1.65 * sigma)
        price_upper = snapshot.last_price * max(0.0, 1.0 + expected_return + 1.65 * sigma)
        volume_spread = min(0.90, 0.15 + 0.45 * time_scale)
        volatility_spread = min(0.70, 0.10 + 0.30 * time_scale)
        risk_score = min(
            100.0,
            max(
                0.0,
                snapshot.risk_score
                + snapshot.annualized_volatility * 15.0 * time_scale
                + abs(expected_return) * 20.0,
            ),
        )
        predictions.append(
            PredictionInterval(
                horizon=horizon,
                price_lower=round(price_lower, 4),
                price_mid=round(price_mid, 4),
                price_upper=round(price_upper, 4),
                volume_lower=round(snapshot.avg_volume_20d * (1.0 - volume_spread), 2),
                volume_mid=round(snapshot.avg_volume_20d, 2),
                volume_upper=round(snapshot.avg_volume_20d * (1.0 + volume_spread), 2),
                volatility_lower=round(
                    snapshot.annualized_volatility * (1.0 - volatility_spread), 6
                ),
                volatility_mid=round(snapshot.annualized_volatility, 6),
                volatility_upper=round(
                    snapshot.annualized_volatility * (1.0 + volatility_spread), 6
                ),
                risk_score=round(risk_score, 4),
            )
        )
    return predictions


def predict_many(
    registry: ModelRegistry, snapshots: Iterable[FeatureSnapshot]
) -> Dict[str, List[PredictionInterval]]:
    output: Dict[str, List[PredictionInterval]] = {}
    for snapshot in snapshots:
        output[snapshot.security_id] = predict_security_metrics(
            registry.active_for(snapshot.security_id), snapshot
        )
    return output

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional, Tuple

from silver_platter.ml import HORIZON_DAYS, FeatureSnapshot, ModelRegistry, PredictionInterval, predict_security_metrics


@dataclass(frozen=True)
class WatchlistItem:
    user_id: str
    security_id: str
    created_at: datetime
    is_active: bool = True
    note: str = ""


@dataclass
class WatchlistRegistry:
    items: Dict[Tuple[str, str], WatchlistItem] = field(default_factory=dict)

    def add(self, user_id: str, security_id: str, note: str = "") -> WatchlistItem:
        item = WatchlistItem(
            user_id=user_id,
            security_id=security_id,
            created_at=datetime.utcnow(),
            note=note,
        )
        self.items[(user_id, security_id)] = item
        return item

    def remove(self, user_id: str, security_id: str) -> Optional[WatchlistItem]:
        current = self.items.get((user_id, security_id))
        if current is None:
            return None
        item = WatchlistItem(
            user_id=current.user_id,
            security_id=current.security_id,
            created_at=current.created_at,
            is_active=False,
            note=current.note,
        )
        self.items[(user_id, security_id)] = item
        return item

    def list_active(self, user_id: str) -> List[WatchlistItem]:
        return sorted(
            [
                item
                for item in self.items.values()
                if item.user_id == user_id and item.is_active
            ],
            key=lambda item: item.security_id,
        )


@dataclass(frozen=True)
class MlPredictionJob:
    job_id: str
    security_id: str
    requested_at: datetime
    horizons: Tuple[str, ...]
    status: str = "pending"


@dataclass(frozen=True)
class StoredPrediction:
    prediction_id: str
    job_id: str
    security_id: str
    as_of: datetime
    horizon: str
    target_at: datetime
    interval: PredictionInterval
    actual_price: Optional[float] = None
    absolute_error: Optional[float] = None
    pct_error: Optional[float] = None


@dataclass(frozen=True)
class PredictionActual:
    prediction_id: str
    actual_price: float
    observed_at: datetime


@dataclass(frozen=True)
class ModelErrorSummary:
    security_id: str
    sample_count: int
    mean_absolute_error: float
    mean_absolute_pct_error: float


def create_prediction_job(
    job_id: str, security_id: str, horizons: Iterable[str], requested_at: Optional[datetime] = None
) -> MlPredictionJob:
    selected_horizons = tuple(horizon for horizon in horizons if horizon in HORIZON_DAYS)
    if not selected_horizons:
        raise ValueError("at least one supported horizon is required")
    return MlPredictionJob(
        job_id=job_id,
        security_id=security_id,
        requested_at=requested_at or datetime.utcnow(),
        horizons=selected_horizons,
    )


def run_prediction_job(
    job: MlPredictionJob,
    snapshot: FeatureSnapshot,
    registry: Optional[ModelRegistry] = None,
) -> List[StoredPrediction]:
    if job.security_id != snapshot.security_id:
        raise ValueError("job security_id must match snapshot security_id")
    model_registry = registry or ModelRegistry()
    model = model_registry.active_for(snapshot.security_id)
    model = type(model)(
        security_id=model.security_id,
        model_id=model.model_id,
        version=model.version,
        horizons=job.horizons,
        fine_tuned=model.fine_tuned,
        status=model.status,
    )
    predictions = predict_security_metrics(model, snapshot)
    return [
        StoredPrediction(
            prediction_id="%s-%s" % (job.job_id, prediction.horizon),
            job_id=job.job_id,
            security_id=job.security_id,
            as_of=snapshot.as_of,
            horizon=prediction.horizon,
            target_at=snapshot.as_of + timedelta(days=HORIZON_DAYS[prediction.horizon]),
            interval=prediction,
        )
        for prediction in predictions
    ]


def attach_prediction_actual(
    prediction: StoredPrediction, actual: PredictionActual
) -> StoredPrediction:
    if prediction.prediction_id != actual.prediction_id:
        raise ValueError("actual prediction_id must match prediction")
    absolute_error = abs(actual.actual_price - prediction.interval.price_mid)
    pct_error = absolute_error / actual.actual_price if actual.actual_price else 0.0
    return StoredPrediction(
        prediction_id=prediction.prediction_id,
        job_id=prediction.job_id,
        security_id=prediction.security_id,
        as_of=prediction.as_of,
        horizon=prediction.horizon,
        target_at=prediction.target_at,
        interval=prediction.interval,
        actual_price=round(actual.actual_price, 4),
        absolute_error=round(absolute_error, 4),
        pct_error=round(pct_error, 6),
    )


def summarize_prediction_errors(
    predictions: Iterable[StoredPrediction], security_id: str
) -> ModelErrorSummary:
    completed = [
        prediction
        for prediction in predictions
        if prediction.security_id == security_id and prediction.absolute_error is not None
    ]
    if not completed:
        return ModelErrorSummary(security_id, 0, 0.0, 0.0)
    mae = sum(prediction.absolute_error or 0.0 for prediction in completed) / len(completed)
    mape = sum(prediction.pct_error or 0.0 for prediction in completed) / len(completed)
    return ModelErrorSummary(
        security_id=security_id,
        sample_count=len(completed),
        mean_absolute_error=round(mae, 4),
        mean_absolute_pct_error=round(mape, 6),
    )

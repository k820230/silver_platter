from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from silver_platter.data_quality import PriceBarInput
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

    def save_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        records = [
            {
                "user_id": item.user_id,
                "security_id": item.security_id,
                "created_at": item.created_at.isoformat(),
                "is_active": item.is_active,
                "note": item.note,
            }
            for item in sorted(
                self.items.values(),
                key=lambda item: (item.user_id, item.security_id),
            )
        ]
        path.write_text(
            json.dumps(records, ensure_ascii=True, sort_keys=True, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load_json(cls, path: Path) -> "WatchlistRegistry":
        if not path.exists():
            return cls()
        records = json.loads(path.read_text(encoding="utf-8"))
        registry = cls()
        if not isinstance(records, list):
            raise ValueError("watchlist registry json must be a list")
        for record in records:
            if not isinstance(record, dict):
                raise ValueError("watchlist registry entry must be an object")
            item = WatchlistItem(
                user_id=str(record["user_id"]),
                security_id=str(record["security_id"]),
                created_at=datetime.fromisoformat(str(record["created_at"])),
                is_active=bool(record.get("is_active", True)),
                note=str(record.get("note", "")),
            )
            registry.items[(item.user_id, item.security_id)] = item
        return registry


@dataclass(frozen=True)
class MlPredictionJob:
    job_id: str
    security_id: str
    requested_at: datetime
    horizons: Tuple[str, ...]
    status: str = "pending"


@dataclass(frozen=True)
class QueuedPredictionJob:
    job: MlPredictionJob
    snapshot: FeatureSnapshot
    enqueued_at: datetime


@dataclass
class InMemoryPredictionJobQueue:
    jobs: List[QueuedPredictionJob] = field(default_factory=list)

    def enqueue(self, job: MlPredictionJob, snapshot: FeatureSnapshot) -> QueuedPredictionJob:
        if job.security_id != snapshot.security_id:
            raise ValueError("job security_id must match snapshot security_id")
        queued = QueuedPredictionJob(
            job=job,
            snapshot=snapshot,
            enqueued_at=datetime.utcnow(),
        )
        self.jobs.append(queued)
        return queued

    def dequeue(self) -> Optional[QueuedPredictionJob]:
        if not self.jobs:
            return None
        return self.jobs.pop(0)

    def run_next(self, registry: Optional[ModelRegistry] = None) -> Optional[List["StoredPrediction"]]:
        queued = self.dequeue()
        if queued is None:
            return None
        return run_prediction_job(queued.job, queued.snapshot, registry)

    def pending_count(self) -> int:
        return len(self.jobs)


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


def enqueue_prediction_job(queue: object, job: MlPredictionJob, snapshot: FeatureSnapshot) -> object:
    if job.security_id != snapshot.security_id:
        raise ValueError("job security_id must match snapshot security_id")
    return queue.enqueue(run_prediction_job, job, snapshot)


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


def match_due_prediction_actuals(
    predictions: Iterable[StoredPrediction],
    price_bars: Iterable[PriceBarInput],
    observed_at: datetime,
) -> List[StoredPrediction]:
    bars_by_security: Dict[str, List[PriceBarInput]] = {}
    for bar in price_bars:
        if (
            bar.close_price is None
            or bar.close_price <= 0
            or bar.available_to_model_at is None
            or bar.available_to_model_at > observed_at
        ):
            continue
        bars_by_security.setdefault(bar.security_id, []).append(bar)
    for bars in bars_by_security.values():
        bars.sort(key=lambda item: (item.bar_ts, item.available_to_model_at))

    matched: List[StoredPrediction] = []
    for prediction in predictions:
        if prediction.actual_price is not None or prediction.target_at > observed_at:
            matched.append(prediction)
            continue
        candidate = next(
            (
                bar
                for bar in bars_by_security.get(prediction.security_id, [])
                if bar.bar_ts >= prediction.target_at
            ),
            None,
        )
        if candidate is None:
            matched.append(prediction)
            continue
        matched.append(
            attach_prediction_actual(
                prediction,
                PredictionActual(
                    prediction_id=prediction.prediction_id,
                    actual_price=float(candidate.close_price),
                    observed_at=candidate.available_to_model_at,
                ),
            )
        )
    return matched


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

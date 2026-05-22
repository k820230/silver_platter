from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional


@dataclass(frozen=True)
class IndexObservation:
    security_id: str
    observed_at: datetime
    volatility_index: float
    risk_score: float


@dataclass(frozen=True)
class IndexChartPoint:
    observed_at: datetime
    volatility_index: float
    risk_score: float


@dataclass(frozen=True)
class IndexChartSeries:
    security_id: str
    points: List[IndexChartPoint]
    start_at: Optional[datetime]
    end_at: Optional[datetime]

    def as_dict(self) -> dict:
        return {
            "security_id": self.security_id,
            "start_at": None if self.start_at is None else self.start_at.isoformat(),
            "end_at": None if self.end_at is None else self.end_at.isoformat(),
            "points": [
                {
                    "observed_at": point.observed_at.isoformat(),
                    "volatility_index": point.volatility_index,
                    "risk_score": point.risk_score,
                }
                for point in self.points
            ],
        }


def build_index_chart_series(
    observations: Iterable[IndexObservation],
    security_id: str,
    start_at: Optional[datetime] = None,
    end_at: Optional[datetime] = None,
) -> IndexChartSeries:
    selected = []
    for observation in observations:
        if observation.security_id != security_id:
            continue
        if start_at is not None and observation.observed_at < start_at:
            continue
        if end_at is not None and observation.observed_at > end_at:
            continue
        selected.append(observation)
    selected.sort(key=lambda item: item.observed_at)
    return IndexChartSeries(
        security_id=security_id,
        points=[
            IndexChartPoint(
                observed_at=item.observed_at,
                volatility_index=round(item.volatility_index, 4),
                risk_score=round(item.risk_score, 4),
            )
            for item in selected
        ],
        start_at=start_at,
        end_at=end_at,
    )

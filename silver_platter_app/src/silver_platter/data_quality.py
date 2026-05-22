from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, List, Optional, Set, Tuple


OK = "ok"
DEGRADED = "degraded"
RISK = "risk"


@dataclass(frozen=True)
class PriceBarInput:
    security_id: str
    bar_ts: datetime
    close_price: Optional[float]
    volume: Optional[float]
    turnover_krw: Optional[float]
    available_to_model_at: Optional[datetime]


@dataclass(frozen=True)
class DataQualityIssue:
    code: str
    severity: str
    message: str


@dataclass(frozen=True)
class DataQualityResult:
    status: str
    issues: List[DataQualityIssue] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "issues": [issue.__dict__ for issue in self.issues],
        }


def evaluate_price_bars(bars: Iterable[PriceBarInput]) -> DataQualityResult:
    issues: List[DataQualityIssue] = []
    seen_keys: Set[Tuple[str, datetime]] = set()
    row_count = 0

    for bar in bars:
        row_count += 1
        key = (bar.security_id, bar.bar_ts)
        if key in seen_keys:
            issues.append(
                DataQualityIssue(
                    "DUPLICATE_BAR",
                    RISK,
                    "duplicate security_id and bar_ts in price bars",
                )
            )
        seen_keys.add(key)

        if bar.close_price is None or bar.close_price <= 0:
            issues.append(
                DataQualityIssue(
                    "INVALID_CLOSE",
                    RISK,
                    "close price is required and must be positive",
                )
            )
        if bar.volume is None or bar.volume < 0:
            issues.append(
                DataQualityIssue(
                    "INVALID_VOLUME",
                    DEGRADED,
                    "volume is missing or negative",
                )
            )
        if bar.turnover_krw is None:
            issues.append(
                DataQualityIssue(
                    "MISSING_TURNOVER",
                    DEGRADED,
                    "turnover_krw is required for liquidity gate",
                )
            )
        if bar.available_to_model_at is None:
            issues.append(
                DataQualityIssue(
                    "MISSING_AVAILABLE_TO_MODEL_AT",
                    RISK,
                    "available_to_model_at is required to prevent lookahead bias",
                )
            )

    if row_count == 0:
        issues.append(DataQualityIssue("EMPTY_DATASET", RISK, "dataset has no rows"))

    if any(issue.severity == RISK for issue in issues):
        status = RISK
    elif issues:
        status = DEGRADED
    else:
        status = OK
    return DataQualityResult(status=status, issues=issues)

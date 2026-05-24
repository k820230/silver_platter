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
class CorporateActionAdjustment:
    security_id: str
    effective_at: datetime
    action_type: str
    price_multiplier: float
    volume_multiplier: float = 1.0


@dataclass(frozen=True)
class DataQualityIssue:
    code: str
    severity: str
    message: str


@dataclass(frozen=True)
class DataQualityResult:
    status: str
    issues: List[DataQualityIssue] = field(default_factory=list)
    score: int = 100

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "score": self.score,
            "issues": [issue.__dict__ for issue in self.issues],
        }


def _quality_score(issues: Iterable[DataQualityIssue]) -> int:
    score = 100
    for issue in issues:
        if issue.severity == RISK:
            score -= 25
        elif issue.severity == DEGRADED:
            score -= 10
    return max(0, score)


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
    return DataQualityResult(status=status, issues=issues, score=_quality_score(issues))


def calculate_average_turnover_krw(
    bars: Iterable[PriceBarInput],
    window: int = 20,
) -> float:
    if window <= 0:
        raise ValueError("window must be positive")
    valid_bars = sorted(
        [bar for bar in bars if bar.turnover_krw is not None],
        key=lambda item: item.bar_ts,
    )
    selected = valid_bars[-window:]
    if not selected:
        return 0.0
    return round(sum(float(bar.turnover_krw or 0.0) for bar in selected) / len(selected), 4)


def apply_corporate_action_adjustments(
    bars: Iterable[PriceBarInput],
    adjustments: Iterable[CorporateActionAdjustment],
) -> List[PriceBarInput]:
    adjustment_list = sorted(adjustments, key=lambda item: item.effective_at)
    adjusted: List[PriceBarInput] = []
    for bar in bars:
        price_multiplier = 1.0
        volume_multiplier = 1.0
        for adjustment in adjustment_list:
            if adjustment.security_id != bar.security_id or bar.bar_ts >= adjustment.effective_at:
                continue
            if adjustment.price_multiplier <= 0 or adjustment.volume_multiplier <= 0:
                raise ValueError("corporate action multipliers must be positive")
            price_multiplier *= adjustment.price_multiplier
            volume_multiplier *= adjustment.volume_multiplier
        close_price = (
            None
            if bar.close_price is None
            else round(float(bar.close_price) * price_multiplier, 6)
        )
        volume = (
            None
            if bar.volume is None
            else round(float(bar.volume) * volume_multiplier, 6)
        )
        if price_multiplier == 1.0 and volume_multiplier == 1.0:
            turnover_krw = bar.turnover_krw
        elif close_price is None or volume is None:
            turnover_krw = None
        else:
            turnover_krw = round(close_price * volume, 4)
        adjusted.append(
            PriceBarInput(
                security_id=bar.security_id,
                bar_ts=bar.bar_ts,
                close_price=close_price,
                volume=volume,
                turnover_krw=turnover_krw,
                available_to_model_at=bar.available_to_model_at,
            )
        )
    return adjusted

from dataclasses import dataclass
from datetime import date
from typing import Iterable, List, Optional


@dataclass(frozen=True)
class DisclosureReaction:
    disclosure_type: str
    disclosed_date: date
    reaction_window_days: int
    return_pct: float
    volume_change_pct: float = 0.0


@dataclass(frozen=True)
class DisclosureImpactPattern:
    disclosure_type: str
    sample_count: int
    avg_return_pct: float
    min_return_pct: float
    max_return_pct: float
    avg_volume_change_pct: float
    expected_impact_days: int


@dataclass(frozen=True)
class DisclosureImpactPrediction:
    disclosure_type: str
    current_price: float
    expected_price_lower: float
    expected_price_mid: float
    expected_price_upper: float
    expected_impact_days: int
    sample_count: int


def analyze_disclosure_impacts(
    reactions: Iterable[DisclosureReaction], disclosure_type: Optional[str] = None
) -> DisclosureImpactPattern:
    selected: List[DisclosureReaction] = [
        reaction
        for reaction in reactions
        if disclosure_type is None or reaction.disclosure_type == disclosure_type
    ]
    if not selected:
        raise ValueError("at least one disclosure reaction is required")
    avg_return = sum(reaction.return_pct for reaction in selected) / len(selected)
    avg_volume = sum(reaction.volume_change_pct for reaction in selected) / len(selected)
    expected_days = round(
        sum(reaction.reaction_window_days for reaction in selected) / len(selected)
    )
    return DisclosureImpactPattern(
        disclosure_type=disclosure_type or selected[0].disclosure_type,
        sample_count=len(selected),
        avg_return_pct=round(avg_return, 6),
        min_return_pct=round(min(reaction.return_pct for reaction in selected), 6),
        max_return_pct=round(max(reaction.return_pct for reaction in selected), 6),
        avg_volume_change_pct=round(avg_volume, 6),
        expected_impact_days=max(1, expected_days),
    )


def predict_disclosure_impact(
    current_price: float, pattern: DisclosureImpactPattern
) -> DisclosureImpactPrediction:
    if current_price <= 0:
        raise ValueError("current_price must be positive")
    return DisclosureImpactPrediction(
        disclosure_type=pattern.disclosure_type,
        current_price=round(current_price, 4),
        expected_price_lower=round(current_price * (1.0 + pattern.min_return_pct), 4),
        expected_price_mid=round(current_price * (1.0 + pattern.avg_return_pct), 4),
        expected_price_upper=round(current_price * (1.0 + pattern.max_return_pct), 4),
        expected_impact_days=pattern.expected_impact_days,
        sample_count=pattern.sample_count,
    )

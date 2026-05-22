from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple


TRUSTED_PROVIDER_NAMES = {
    "bloomberg",
    "dow_jones",
    "factset",
    "krx_kind",
    "lseg",
    "opendart",
    "sec_edgar",
}

GEOPOLITICAL_TAGS = {
    "geopolitical",
    "war",
    "sanction",
    "terror",
    "diplomacy",
    "energy_security",
}


@dataclass(frozen=True)
class Headline:
    provider: str
    title: str
    published_at: datetime
    url: str
    security_ids: Tuple[str, ...] = ()
    group_ids: Tuple[str, ...] = ()
    event_tags: Tuple[str, ...] = ()
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class EventMarketSnapshot:
    event_id: str
    observed_at: datetime
    event_tags: Tuple[str, ...]
    five_min_avg_volume: float
    previous_5d_five_min_avg_volume: float
    title: str = ""


@dataclass(frozen=True)
class RealtimeAlert:
    alert_id: str
    severity: str
    message: str
    observed_at: datetime
    volume_increase_pct: float
    event_tags: Tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "severity": self.severity,
            "message": self.message,
            "observed_at": self.observed_at.isoformat(),
            "volume_increase_pct": self.volume_increase_pct,
            "event_tags": list(self.event_tags),
        }


def is_trusted_headline(headline: Headline) -> bool:
    return headline.provider.strip().lower() in TRUSTED_PROVIDER_NAMES


def reliable_headlines(headlines: Iterable[Headline]) -> List[Headline]:
    return sorted(
        [headline for headline in headlines if is_trusted_headline(headline)],
        key=lambda item: item.published_at,
        reverse=True,
    )


def group_headlines_by_business_group(
    headlines: Iterable[Headline], limit_per_group: int = 20
) -> Dict[str, List[Headline]]:
    grouped: Dict[str, List[Headline]] = {}
    for headline in reliable_headlines(headlines):
        for group_id in headline.group_ids:
            grouped.setdefault(group_id, []).append(headline)
    return {
        group_id: items[:limit_per_group]
        for group_id, items in sorted(grouped.items(), key=lambda item: item[0])
    }


def detect_geopolitical_market_alert(
    snapshot: EventMarketSnapshot, volume_threshold_multiple: float = 2.0
) -> Optional[RealtimeAlert]:
    if snapshot.previous_5d_five_min_avg_volume <= 0:
        return None
    normalized_tags = {
        tag.strip().lower() for tag in snapshot.event_tags if tag.strip()
    }
    if not normalized_tags.intersection(GEOPOLITICAL_TAGS):
        return None
    volume_multiple = (
        snapshot.five_min_avg_volume / snapshot.previous_5d_five_min_avg_volume
    )
    if volume_multiple < volume_threshold_multiple:
        return None
    increase_pct = (volume_multiple - 1.0) * 100.0
    severity = "critical" if volume_multiple >= 3.0 else "warning"
    return RealtimeAlert(
        alert_id="geo-%s" % snapshot.event_id,
        severity=severity,
        message="international event volume shock detected",
        observed_at=snapshot.observed_at,
        volume_increase_pct=round(increase_pct, 4),
        event_tags=tuple(sorted(normalized_tags)),
    )

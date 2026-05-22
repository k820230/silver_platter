from dataclasses import dataclass, field
from datetime import datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import hashlib
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple


TRUSTED_PROVIDER_NAMES = {
    "bloomberg",
    "dow_jones",
    "ecb",
    "factset",
    "federal_reserve",
    "krx_kind",
    "lseg",
    "opendart",
    "ofac",
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
class OfficialRssSource:
    provider: str
    feed_url: str
    event_tags: Tuple[str, ...] = ()
    security_ids: Tuple[str, ...] = ()
    group_ids: Tuple[str, ...] = ()


TextFetcher = Callable[[str, Dict[str, str]], str]


@dataclass(frozen=True)
class HeadlineDedupCluster:
    cluster_id: str
    representative: Headline
    headlines: Tuple[Headline, ...]
    provider_count: int
    source_urls: Tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "cluster_id": self.cluster_id,
            "representative": {
                "provider": self.representative.provider,
                "title": self.representative.title,
                "published_at": self.representative.published_at.isoformat(),
                "url": self.representative.url,
                "event_tags": list(self.representative.event_tags),
            },
            "provider_count": self.provider_count,
            "source_urls": list(self.source_urls),
            "headline_count": len(self.headlines),
        }


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


def normalized_headline_cluster_key(headline: Headline) -> str:
    normalized_title = re.sub(r"[^a-z0-9]+", " ", headline.title.lower()).strip()
    normalized_title = " ".join(normalized_title.split())
    published_day = headline.published_at.date().isoformat()
    return "%s:%s" % (published_day, normalized_title)


def deduplicate_headlines(headlines: Iterable[Headline]) -> List[HeadlineDedupCluster]:
    grouped: Dict[str, List[Headline]] = {}
    for headline in headlines:
        grouped.setdefault(normalized_headline_cluster_key(headline), []).append(headline)

    clusters: List[HeadlineDedupCluster] = []
    for key, items in grouped.items():
        sorted_items = sorted(
            items,
            key=lambda item: (is_trusted_headline(item), item.published_at),
            reverse=True,
        )
        representative = sorted_items[0]
        cluster_id = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
        clusters.append(
            HeadlineDedupCluster(
                cluster_id=cluster_id,
                representative=representative,
                headlines=tuple(sorted_items),
                provider_count=len({item.provider.strip().lower() for item in sorted_items}),
                source_urls=tuple(sorted({item.url for item in sorted_items if item.url})),
            )
        )
    return sorted(clusters, key=lambda item: item.representative.published_at, reverse=True)


def _default_text_fetcher(url: str, headers: Dict[str, str]) -> str:
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.read().decode("utf-8", errors="replace")


def _xml_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _child_text(element: ET.Element, names: Sequence[str]) -> str:
    wanted = {name.lower() for name in names}
    for child in list(element):
        if _xml_local_name(child.tag) in wanted and child.text:
            return " ".join(child.text.split())
    return ""


def _entry_link(element: ET.Element) -> str:
    direct = _child_text(element, ("link",))
    if direct:
        return direct
    for child in list(element):
        if _xml_local_name(child.tag) == "link":
            href = child.attrib.get("href")
            if href:
                return href.strip()
    return ""


def _parse_feed_timestamp(value: str) -> datetime:
    normalized = value.strip()
    if not normalized:
        return datetime.utcnow()
    try:
        return parsedate_to_datetime(normalized).replace(tzinfo=None)
    except (TypeError, ValueError, IndexError):
        pass
    return datetime.fromisoformat(normalized.replace("Z", "+00:00")).replace(tzinfo=None)


class OfficialRssHeadlineProvider:
    def __init__(
        self,
        source: OfficialRssSource,
        fetcher: TextFetcher = _default_text_fetcher,
    ):
        self.source = source
        self._fetcher = fetcher

    def fetch_headlines(self, limit: Optional[int] = None) -> List[Headline]:
        payload = self._fetcher(
            self.source.feed_url,
            {
                "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
                "User-Agent": "Silver Platter official headline collector",
            },
        )
        root = ET.fromstring(payload)
        entries = self._rss_items(root) or self._atom_entries(root)
        headlines = [self._normalize_entry(entry) for entry in entries]
        return headlines[:limit] if limit is not None else headlines

    def _rss_items(self, root: ET.Element) -> List[ET.Element]:
        return [element for element in root.iter() if _xml_local_name(element.tag) == "item"]

    def _atom_entries(self, root: ET.Element) -> List[ET.Element]:
        return [element for element in root.iter() if _xml_local_name(element.tag) == "entry"]

    def _normalize_entry(self, entry: ET.Element) -> Headline:
        title = _child_text(entry, ("title",))
        url = _entry_link(entry)
        published = _child_text(entry, ("pubDate", "published", "updated"))
        raw_ref = _child_text(entry, ("guid", "id")) or url or title
        return Headline(
            provider=self.source.provider,
            title=title,
            published_at=_parse_feed_timestamp(published),
            url=url,
            security_ids=self.source.security_ids,
            group_ids=self.source.group_ids,
            event_tags=self.source.event_tags,
            metadata={
                "raw_ref": raw_ref,
                "feed_url": self.source.feed_url,
            },
        )


def default_official_rss_sources() -> List[OfficialRssSource]:
    return [
        OfficialRssSource(
            provider="federal_reserve",
            feed_url="https://www.federalreserve.gov/feeds/press_all.xml",
            event_tags=("central_bank", "monetary_policy"),
        ),
        OfficialRssSource(
            provider="ecb",
            feed_url="https://www.ecb.europa.eu/rss/press.html",
            event_tags=("central_bank", "monetary_policy"),
        ),
    ]


class _OfacRecentActionsParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows: List[Dict[str, object]] = []
        self._row: Optional[Dict[str, object]] = None
        self._depth = 0

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        attributes = dict(attrs)
        classes = attributes.get("class", "")
        if self._row is None and tag.lower() == "div":
            class_names = set(classes.split())
            if {"search-result", "views-row"}.issubset(class_names):
                self._row = {"text": [], "links": []}
                self._depth = 1
                return
        if self._row is not None:
            if tag.lower() == "div":
                self._depth += 1
            if tag.lower() == "a":
                href = attributes.get("href")
                if href:
                    self._row["links"].append(href)

    def handle_data(self, data: str) -> None:
        if self._row is not None:
            text = " ".join(data.split())
            if text:
                self._row["text"].append(text)

    def handle_endtag(self, tag: str) -> None:
        if self._row is None or tag.lower() != "div":
            return
        self._depth -= 1
        if self._depth == 0:
            self.rows.append(self._row)
            self._row = None


def _parse_ofac_date(value: str) -> datetime:
    return datetime.strptime(value, "%B %d, %Y")


class OfacRecentActionsHeadlineProvider:
    def __init__(
        self,
        fetcher: TextFetcher = _default_text_fetcher,
        base_url: str = "https://ofac.treasury.gov/recent-actions",
    ):
        self._fetcher = fetcher
        self._base_url = base_url

    def fetch_headlines(self, limit: Optional[int] = None) -> List[Headline]:
        payload = self._fetcher(
            self._base_url,
            {
                "Accept": "text/html",
                "User-Agent": "Silver Platter OFAC recent actions collector",
            },
        )
        parser = _OfacRecentActionsParser()
        parser.feed(payload)
        headlines = [self._normalize_row(row) for row in parser.rows]
        return headlines[:limit] if limit is not None else headlines

    def _normalize_row(self, row: Dict[str, object]) -> Headline:
        text_parts = [str(value) for value in row.get("text", [])]
        links = [str(value) for value in row.get("links", [])]
        title = text_parts[0] if text_parts else ""
        detail_url = urllib.parse.urljoin(self._base_url, links[0]) if links else self._base_url
        category = text_parts[-1] if len(text_parts) >= 2 else ""
        date_value = ""
        for text in text_parts:
            match = re.search(r"[A-Z][a-z]+ \d{1,2}, \d{4}", text)
            if match:
                date_value = match.group(0)
                break
        published_at = _parse_ofac_date(date_value) if date_value else datetime.utcnow()
        return Headline(
            provider="ofac",
            title=title,
            published_at=published_at,
            url=detail_url,
            event_tags=("geopolitical", "sanction"),
            metadata={
                "category": category,
                "raw_ref": detail_url,
                "source": "OFAC Recent Actions",
            },
        )


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

from dataclasses import asdict, dataclass
from datetime import date, datetime
import hashlib
import json
from typing import Iterable, List, Optional, Sequence

from silver_platter.data_quality import DataQualityResult, PriceBarInput, evaluate_price_bars
from silver_platter.providers import (
    DisclosureMetadataInput,
    DisclosureMetadataProvider,
    FxRateInput,
    FxRateProvider,
    MarketDataProvider,
    ProviderMetadata,
    ReferenceDataProvider,
    SecurityReference,
)


@dataclass(frozen=True)
class RawDataManifest:
    provider_code: str
    dataset_name: str
    source_uri: Optional[str]
    storage_uri: str
    content_sha256: str
    row_count: int
    quality_status: str
    loaded_at: datetime

    def as_dict(self) -> dict:
        return {
            "provider_code": self.provider_code,
            "dataset_name": self.dataset_name,
            "source_uri": self.source_uri,
            "storage_uri": self.storage_uri,
            "content_sha256": self.content_sha256,
            "row_count": self.row_count,
            "quality_status": self.quality_status,
            "loaded_at": self.loaded_at.isoformat(),
        }


@dataclass(frozen=True)
class PriceBarIngestionResult:
    provider: ProviderMetadata
    dataset_name: str
    bars: List[PriceBarInput]
    quality: DataQualityResult
    manifest: RawDataManifest


@dataclass(frozen=True)
class ReferenceDataIngestionResult:
    provider: ProviderMetadata
    securities: List[SecurityReference]
    manifest: RawDataManifest


@dataclass(frozen=True)
class DisclosureIngestionResult:
    provider: ProviderMetadata
    disclosures: List[DisclosureMetadataInput]
    manifest: RawDataManifest


@dataclass(frozen=True)
class FxIngestionResult:
    provider: ProviderMetadata
    rates: List[FxRateInput]
    manifest: RawDataManifest


def _json_default(value: object) -> str:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _canonical_payload(rows: Sequence[object]) -> str:
    serializable_rows = [asdict(row) if hasattr(row, "__dataclass_fields__") else row for row in rows]
    return json.dumps(
        serializable_rows,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
        default=_json_default,
    )


def build_raw_manifest(
    provider_code: str,
    dataset_name: str,
    rows: Sequence[object],
    storage_uri: str,
    quality_status: str,
    source_uri: Optional[str] = None,
    loaded_at: Optional[datetime] = None,
) -> RawDataManifest:
    payload = _canonical_payload(rows)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return RawDataManifest(
        provider_code=provider_code,
        dataset_name=dataset_name,
        source_uri=source_uri,
        storage_uri=storage_uri,
        content_sha256=digest,
        row_count=len(rows),
        quality_status=quality_status,
        loaded_at=loaded_at or datetime.utcnow(),
    )


def collect_price_bars(
    provider: MarketDataProvider,
    symbol: str,
    dataset_name: str = "price_bar",
    storage_uri: Optional[str] = None,
    source_uri: Optional[str] = None,
) -> PriceBarIngestionResult:
    bars = list(provider.get_price_bars(symbol))
    quality = evaluate_price_bars(bars)
    manifest = build_raw_manifest(
        provider.metadata.provider_code,
        dataset_name,
        bars,
        storage_uri or "memory://%s/%s" % (provider.metadata.provider_code, symbol),
        quality.status,
        source_uri=source_uri,
    )
    return PriceBarIngestionResult(provider.metadata, dataset_name, bars, quality, manifest)


def collect_reference_data(
    provider: ReferenceDataProvider,
    dataset_name: str = "security_reference",
    storage_uri: Optional[str] = None,
) -> ReferenceDataIngestionResult:
    securities = list(provider.get_securities())
    manifest = build_raw_manifest(
        provider.metadata.provider_code,
        dataset_name,
        securities,
        storage_uri or "memory://%s/securities" % provider.metadata.provider_code,
        "ok" if securities else "risk",
    )
    return ReferenceDataIngestionResult(provider.metadata, securities, manifest)


def collect_disclosure_metadata(
    provider: DisclosureMetadataProvider,
    symbol: str,
    dataset_name: str = "disclosure_metadata",
    storage_uri: Optional[str] = None,
) -> DisclosureIngestionResult:
    disclosures = list(provider.get_disclosures(symbol))
    manifest = build_raw_manifest(
        provider.metadata.provider_code,
        dataset_name,
        disclosures,
        storage_uri or "memory://%s/disclosures/%s" % (provider.metadata.provider_code, symbol),
        "ok" if disclosures else "degraded",
    )
    return DisclosureIngestionResult(provider.metadata, disclosures, manifest)


def collect_fx_rates(
    provider: FxRateProvider,
    base_currency: str,
    quote_currency: str,
    dataset_name: str = "fx_rate",
    storage_uri: Optional[str] = None,
) -> FxIngestionResult:
    rates = list(provider.get_rates(base_currency, quote_currency))
    manifest = build_raw_manifest(
        provider.metadata.provider_code,
        dataset_name,
        rates,
        storage_uri
        or "memory://%s/fx/%s%s"
        % (provider.metadata.provider_code, base_currency.upper(), quote_currency.upper()),
        "ok" if rates else "degraded",
    )
    return FxIngestionResult(provider.metadata, rates, manifest)

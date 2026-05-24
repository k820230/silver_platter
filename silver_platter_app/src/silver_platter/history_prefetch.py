from dataclasses import dataclass
from datetime import date
from typing import Optional

from silver_platter.data_pipeline import collect_price_bars
from silver_platter.providers import MarketDataProvider, SecurityReference


@dataclass(frozen=True)
class HistoryPrefetchResult:
    security_id: str
    market_code: str
    provider_code: str
    status: str
    is_new_security: bool
    bar_count: int
    existing_bar_count: int
    quality_status: str
    storage_uri: str
    detail: str = ""

    def as_dict(self) -> dict:
        return {
            "security_id": self.security_id,
            "market_code": self.market_code,
            "provider_code": self.provider_code,
            "status": self.status,
            "is_new_security": self.is_new_security,
            "bar_count": self.bar_count,
            "existing_bar_count": self.existing_bar_count,
            "quality_status": self.quality_status,
            "storage_uri": self.storage_uri,
            "detail": self.detail,
        }


def infer_security_reference(symbol: str, market_code: str = "") -> SecurityReference:
    normalized_symbol = symbol.strip().upper()
    if not normalized_symbol:
        raise ValueError("security_id is required")

    normalized_market = market_code.strip().upper()
    if not normalized_market:
        normalized_market = _infer_market_code(normalized_symbol)

    provider_symbol = normalized_symbol
    if normalized_market in {"KR", "KRX"} and (
        provider_symbol.endswith(".KS") or provider_symbol.endswith(".KQ")
    ):
        provider_symbol = provider_symbol.rsplit(".", 1)[0]

    if normalized_market in {"KR", "KRX"}:
        return SecurityReference(
            symbol=provider_symbol,
            security_name=provider_symbol,
            market_code="KR",
            country_code="KOR",
            currency="KRW",
            asset_type="stock",
            exchange_code="KRX",
            provider_symbol=provider_symbol,
        )

    return SecurityReference(
        symbol=normalized_symbol,
        security_name=normalized_symbol,
        market_code=normalized_market or "US",
        country_code="USA" if normalized_market == "US" else "",
        currency="USD" if normalized_market == "US" else "",
        asset_type="stock",
        exchange_code=normalized_market or "US",
        provider_symbol=provider_symbol,
    )


class HistoricalPricePrefetcher:
    def __init__(self, repository: object, bar_interval: str = "1d"):
        self.repository = repository
        self.bar_interval = bar_interval

    def prefetch(
        self,
        symbol: str,
        provider: MarketDataProvider,
        market_code: str = "",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        target_bar_count: int = 1,
    ) -> HistoryPrefetchResult:
        if target_bar_count <= 0:
            raise ValueError("target_bar_count must be positive")
        security = infer_security_reference(symbol, market_code)
        provider_id = self.repository.ensure_provider_id(provider.metadata)
        existing_security_id = self.repository.get_security_id(
            security.market_code,
            security.symbol,
        )
        is_new_security = existing_security_id is None
        security_db_id = self.repository.ensure_security_id(security)
        existing_bar_count = self.repository.count_price_bars(
            security_db_id,
            provider_id,
            self.bar_interval,
        )
        storage_uri = _storage_uri(security, provider.metadata.provider_code)
        if existing_bar_count >= target_bar_count:
            self.repository.commit()
            return HistoryPrefetchResult(
                security_id=security.symbol,
                market_code=security.market_code,
                provider_code=provider.metadata.provider_code,
                status="skipped_existing_history",
                is_new_security=is_new_security,
                bar_count=0,
                existing_bar_count=existing_bar_count,
                quality_status="ok",
                storage_uri=storage_uri,
                detail="price history already has at least %s bars in DB"
                % target_bar_count,
            )

        ingestion = collect_price_bars(
            provider,
            security.provider_symbol,
            storage_uri=storage_uri,
            source_uri=_source_uri(provider.metadata.provider_code, security, start_date, end_date),
        )
        self.repository.write_price_bar_ingestion(
            provider_id,
            security_db_id,
            ingestion,
            self.bar_interval,
        )
        self.repository.commit()
        return HistoryPrefetchResult(
            security_id=security.symbol,
            market_code=security.market_code,
            provider_code=provider.metadata.provider_code,
            status="stored" if ingestion.bars else "no_data",
            is_new_security=is_new_security,
            bar_count=len(ingestion.bars),
            existing_bar_count=existing_bar_count,
            quality_status=ingestion.quality.status,
            storage_uri=storage_uri,
            detail="stored historical price bars in DB"
            if ingestion.bars
            else "provider returned no price bars",
        )


def _infer_market_code(symbol: str) -> str:
    if symbol.endswith(".KS") or symbol.endswith(".KQ"):
        return "KR"
    if symbol.isdigit() and len(symbol) == 6:
        return "KR"
    return "US"


def _storage_uri(security: SecurityReference, provider_code: str) -> str:
    return "goldilocks://SP.price_bar/%s/%s/%s" % (
        provider_code,
        security.market_code,
        security.symbol,
    )


def _source_uri(
    provider_code: str,
    security: SecurityReference,
    start_date: Optional[date],
    end_date: Optional[date],
) -> str:
    if start_date is None or end_date is None:
        return "provider://%s/%s" % (provider_code, security.provider_symbol)
    return "provider://%s/%s?from=%s&to=%s" % (
        provider_code,
        security.provider_symbol,
        start_date.isoformat(),
        end_date.isoformat(),
    )

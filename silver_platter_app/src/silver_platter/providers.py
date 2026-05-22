from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, List, Optional, Sequence, Tuple

from silver_platter.data_quality import PriceBarInput


@dataclass(frozen=True)
class ProviderMetadata:
    provider_code: str
    provider_type: str
    can_store: bool
    can_display_realtime: bool
    can_redistribute: bool
    priority: int = 100


@dataclass(frozen=True)
class SecurityReference:
    symbol: str
    security_name: str
    market_code: str
    country_code: str
    currency: str
    asset_type: str
    exchange_code: str
    provider_symbol: str
    standard_industry_code: Optional[str] = None
    business_tags: Tuple[str, ...] = ()


@dataclass(frozen=True)
class DisclosureMetadataInput:
    provider_event_id: str
    security_id: str
    disclosure_type: str
    title: str
    disclosed_at: datetime
    source_url: str
    metadata: Tuple[Tuple[str, str], ...] = ()


@dataclass(frozen=True)
class FxRateInput:
    base_currency: str
    quote_currency: str
    rate_date: date
    rate: float
    provider_code: str
    source_priority: int = 100


class MarketDataProvider(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        raise NotImplementedError

    @abstractmethod
    def get_price_bars(self, symbol: str) -> Iterable[PriceBarInput]:
        raise NotImplementedError


class ReferenceDataProvider(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        raise NotImplementedError

    @abstractmethod
    def get_securities(self) -> Iterable[SecurityReference]:
        raise NotImplementedError


class DisclosureMetadataProvider(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        raise NotImplementedError

    @abstractmethod
    def get_disclosures(self, symbol: str) -> Iterable[DisclosureMetadataInput]:
        raise NotImplementedError


class FxRateProvider(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        raise NotImplementedError

    @abstractmethod
    def get_rates(
        self, base_currency: str, quote_currency: str
    ) -> Iterable[FxRateInput]:
        raise NotImplementedError


class StaticMarketDataProvider(MarketDataProvider):
    def __init__(self, provider_code: str, bars: List[PriceBarInput]):
        self._metadata = ProviderMetadata(
            provider_code=provider_code,
            provider_type="market_data",
            can_store=True,
            can_display_realtime=False,
            can_redistribute=False,
        )
        self._bars = bars

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    def get_price_bars(self, symbol: str) -> Iterable[PriceBarInput]:
        return [bar for bar in self._bars if bar.security_id == symbol]


class StaticReferenceDataProvider(ReferenceDataProvider):
    def __init__(self, provider_code: str, securities: Sequence[SecurityReference]):
        self._metadata = ProviderMetadata(
            provider_code=provider_code,
            provider_type="reference_data",
            can_store=True,
            can_display_realtime=False,
            can_redistribute=False,
        )
        self._securities = list(securities)

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    def get_securities(self) -> Iterable[SecurityReference]:
        return list(self._securities)


class StaticDisclosureMetadataProvider(DisclosureMetadataProvider):
    def __init__(
        self, provider_code: str, disclosures: Sequence[DisclosureMetadataInput]
    ):
        self._metadata = ProviderMetadata(
            provider_code=provider_code,
            provider_type="disclosure",
            can_store=True,
            can_display_realtime=False,
            can_redistribute=False,
        )
        self._disclosures = list(disclosures)

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    def get_disclosures(self, symbol: str) -> Iterable[DisclosureMetadataInput]:
        return [
            disclosure
            for disclosure in self._disclosures
            if disclosure.security_id == symbol
        ]


class StaticFxRateProvider(FxRateProvider):
    def __init__(self, provider_code: str, rates: Sequence[FxRateInput]):
        self._metadata = ProviderMetadata(
            provider_code=provider_code,
            provider_type="fx",
            can_store=True,
            can_display_realtime=False,
            can_redistribute=False,
        )
        self._rates = list(rates)

    @property
    def metadata(self) -> ProviderMetadata:
        return self._metadata

    def get_rates(
        self, base_currency: str, quote_currency: str
    ) -> Iterable[FxRateInput]:
        base = base_currency.strip().upper()
        quote = quote_currency.strip().upper()
        return [
            rate
            for rate in self._rates
            if rate.base_currency.strip().upper() == base
            and rate.quote_currency.strip().upper() == quote
        ]


def sample_bar(symbol: str, ts: datetime, close: float) -> PriceBarInput:
    return PriceBarInput(
        security_id=symbol,
        bar_ts=ts,
        close_price=close,
        volume=1000,
        turnover_krw=close * 1000,
        available_to_model_at=ts,
    )


def default_mvp_provider_catalog() -> List[ProviderMetadata]:
    return [
        ProviderMetadata("krx_free", "reference_data", True, False, False, 10),
        ProviderMetadata("krx_free", "market_data", True, False, False, 20),
        ProviderMetadata("opendart", "disclosure", True, False, False, 10),
        ProviderMetadata("krx_kind", "disclosure", True, False, False, 20),
        ProviderMetadata("sec_edgar", "disclosure", True, False, False, 30),
        ProviderMetadata("free_fx_placeholder", "fx", True, False, False, 90),
    ]

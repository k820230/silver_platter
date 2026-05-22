from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List

from silver_platter.data_quality import PriceBarInput


@dataclass(frozen=True)
class ProviderMetadata:
    provider_code: str
    provider_type: str
    can_store: bool
    can_display_realtime: bool
    can_redistribute: bool


class MarketDataProvider(ABC):
    @property
    @abstractmethod
    def metadata(self) -> ProviderMetadata:
        raise NotImplementedError

    @abstractmethod
    def get_price_bars(self, symbol: str) -> Iterable[PriceBarInput]:
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


def sample_bar(symbol: str, ts: datetime, close: float) -> PriceBarInput:
    return PriceBarInput(
        security_id=symbol,
        bar_ts=ts,
        close_price=close,
        volume=1000,
        turnover_krw=close * 1000,
        available_to_model_at=ts,
    )

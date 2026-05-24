from datetime import date, datetime
from unittest import TestCase

from silver_platter.history_prefetch import (
    HistoricalPricePrefetcher,
    infer_security_reference,
)
from silver_platter.providers import StaticMarketDataProvider, sample_bar


class FakeHistoryRepository:
    def __init__(
        self,
        existing_security_id=None,
        security_id=11,
        provider_id=7,
        existing_bar_count=0,
    ):
        self.existing_security_id = existing_security_id
        self.security_id = security_id
        self.provider_id = provider_id
        self.existing_bar_count = existing_bar_count
        self.ingestions = []
        self.commits = 0

    def ensure_provider_id(self, provider):
        self.provider = provider
        return self.provider_id

    def get_security_id(self, market_code, symbol):
        self.looked_up_security = (market_code, symbol)
        return self.existing_security_id

    def ensure_security_id(self, security):
        self.security = security
        return self.security_id

    def count_price_bars(self, security_id, provider_id, bar_interval):
        self.count_args = (security_id, provider_id, bar_interval)
        return self.existing_bar_count

    def write_price_bar_ingestion(self, provider_id, security_id, ingestion, bar_interval):
        self.ingestions.append((provider_id, security_id, ingestion, bar_interval))

    def commit(self):
        self.commits += 1


class HistoryPrefetchTests(TestCase):
    def test_infer_security_reference_normalizes_kr_suffix(self):
        security = infer_security_reference("005930.KS")

        self.assertEqual("005930", security.symbol)
        self.assertEqual("005930", security.provider_symbol)
        self.assertEqual("KR", security.market_code)
        self.assertEqual("KOR", security.country_code)
        self.assertEqual("KRW", security.currency)

    def test_prefetch_stores_new_security_history_in_repository(self):
        repository = FakeHistoryRepository(existing_security_id=None)
        provider = StaticMarketDataProvider(
            "stock_info_api",
            [sample_bar("005930", datetime(2026, 5, 22, 16, 0, 0), 70000.0)],
        )

        result = HistoricalPricePrefetcher(repository).prefetch(
            "005930.KS",
            provider,
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 22),
        )

        self.assertEqual("stored", result.status)
        self.assertTrue(result.is_new_security)
        self.assertEqual(1, result.bar_count)
        self.assertEqual("stock_info_api", result.provider_code)
        self.assertEqual("goldilocks://SP.price_bar/stock_info_api/KR/005930", result.storage_uri)
        self.assertEqual(1, len(repository.ingestions))
        self.assertEqual((7, 11), repository.ingestions[0][:2])
        self.assertEqual("1d", repository.ingestions[0][3])
        self.assertEqual(1, repository.commits)

    def test_prefetch_skips_when_history_already_exists(self):
        repository = FakeHistoryRepository(
            existing_security_id=11,
            existing_bar_count=12,
        )
        provider = StaticMarketDataProvider(
            "stock_info_api",
            [sample_bar("AAPL", datetime(2026, 5, 22, 16, 0, 0), 200.0)],
        )

        result = HistoricalPricePrefetcher(repository).prefetch("AAPL", provider)

        self.assertEqual("skipped_existing_history", result.status)
        self.assertFalse(result.is_new_security)
        self.assertEqual(12, result.existing_bar_count)
        self.assertEqual([], repository.ingestions)
        self.assertEqual(1, repository.commits)

    def test_prefetch_backfills_when_existing_history_is_below_target(self):
        repository = FakeHistoryRepository(
            existing_security_id=11,
            existing_bar_count=12,
        )
        provider = StaticMarketDataProvider(
            "stock_info_api",
            [sample_bar("005930", datetime(2026, 5, 22, 16, 0, 0), 70000.0)],
        )

        result = HistoricalPricePrefetcher(repository).prefetch(
            "005930",
            provider,
            target_bar_count=300,
        )

        self.assertEqual("stored", result.status)
        self.assertEqual(12, result.existing_bar_count)
        self.assertEqual(1, len(repository.ingestions))

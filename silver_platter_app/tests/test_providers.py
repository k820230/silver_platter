from datetime import date, datetime
from unittest import TestCase

from silver_platter.providers import (
    DisclosureMetadataInput,
    FxRateInput,
    SecurityReference,
    StaticDisclosureMetadataProvider,
    StaticFxRateProvider,
    StaticReferenceDataProvider,
    default_mvp_provider_catalog,
)


class ProviderTests(TestCase):
    def test_default_catalog_contains_mvp_free_sources(self):
        catalog = default_mvp_provider_catalog()
        codes = {provider.provider_code for provider in catalog}

        self.assertIn("krx_free", codes)
        self.assertIn("opendart", codes)
        self.assertIn("sec_edgar", codes)
        self.assertIn("free_fx_placeholder", codes)

    def test_static_reference_provider_returns_securities(self):
        provider = StaticReferenceDataProvider(
            "krx_free",
            [
                SecurityReference(
                    symbol="005930",
                    security_name="Samsung Electronics",
                    market_code="KOSPI",
                    country_code="KOR",
                    currency="KRW",
                    asset_type="stock",
                    exchange_code="KRX",
                    provider_symbol="005930",
                )
            ],
        )

        self.assertEqual("reference_data", provider.metadata.provider_type)
        self.assertEqual(1, len(list(provider.get_securities())))

    def test_static_disclosure_provider_filters_by_symbol(self):
        disclosure = DisclosureMetadataInput(
            provider_event_id="dart-1",
            security_id="005930",
            disclosure_type="earnings",
            title="Quarterly report",
            disclosed_at=datetime(2026, 5, 22, 9, 0, 0),
            source_url="https://dart.fss.or.kr/",
        )
        provider = StaticDisclosureMetadataProvider("opendart", [disclosure])

        self.assertEqual([disclosure], list(provider.get_disclosures("005930")))
        self.assertEqual([], list(provider.get_disclosures("000660")))

    def test_static_fx_provider_filters_pair(self):
        rate = FxRateInput("USD", "KRW", date(2026, 5, 22), 1360.0, "free_fx_placeholder")
        provider = StaticFxRateProvider("free_fx_placeholder", [rate])

        self.assertEqual([rate], list(provider.get_rates("usd", "krw")))
        self.assertEqual([], list(provider.get_rates("KRW", "USD")))

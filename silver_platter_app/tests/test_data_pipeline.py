from datetime import date, datetime
from unittest import TestCase

from silver_platter.data_pipeline import (
    build_raw_manifest,
    collect_disclosure_metadata,
    collect_fx_rates,
    collect_price_bars,
    collect_reference_data,
)
from silver_platter.providers import (
    DisclosureMetadataInput,
    FxRateInput,
    SecurityReference,
    StaticDisclosureMetadataProvider,
    StaticFxRateProvider,
    StaticMarketDataProvider,
    StaticReferenceDataProvider,
    sample_bar,
)


class DataPipelineTests(TestCase):
    def test_collect_price_bars_returns_quality_and_manifest(self):
        bar = sample_bar("AAPL", datetime(2026, 5, 22, 9, 0, 0), 200.0)
        result = collect_price_bars(StaticMarketDataProvider("free", [bar]), "AAPL")

        self.assertEqual("ok", result.quality.status)
        self.assertEqual(1, result.manifest.row_count)
        self.assertEqual("price_bar", result.manifest.dataset_name)
        self.assertEqual(64, len(result.manifest.content_sha256))

    def test_manifest_digest_is_stable(self):
        rows = [sample_bar("AAPL", datetime(2026, 5, 22, 9, 0, 0), 200.0)]
        first = build_raw_manifest("free", "price_bar", rows, "memory://a", "ok")
        second = build_raw_manifest("free", "price_bar", rows, "memory://a", "ok")

        self.assertEqual(first.content_sha256, second.content_sha256)

    def test_collect_reference_disclosure_and_fx(self):
        reference_result = collect_reference_data(
            StaticReferenceDataProvider(
                "krx_free",
                [
                    SecurityReference(
                        "005930",
                        "Samsung Electronics",
                        "KOSPI",
                        "KOR",
                        "KRW",
                        "stock",
                        "KRX",
                        "005930",
                    )
                ],
            )
        )
        disclosure_result = collect_disclosure_metadata(
            StaticDisclosureMetadataProvider(
                "opendart",
                [
                    DisclosureMetadataInput(
                        "d1",
                        "005930",
                        "earnings",
                        "Report",
                        datetime(2026, 5, 22, 9, 0, 0),
                        "https://dart.fss.or.kr/",
                    )
                ],
            ),
            "005930",
        )
        fx_result = collect_fx_rates(
            StaticFxRateProvider(
                "free_fx_placeholder",
                [FxRateInput("USD", "KRW", date(2026, 5, 22), 1360.0, "free_fx_placeholder")],
            ),
            "USD",
            "KRW",
        )

        self.assertEqual("ok", reference_result.manifest.quality_status)
        self.assertEqual("ok", disclosure_result.manifest.quality_status)
        self.assertEqual("ok", fx_result.manifest.quality_status)

from datetime import date
from unittest import TestCase

from silver_platter.tax import OverseasRealizedTrade, estimate_overseas_capital_gains_tax


class TaxTests(TestCase):
    def test_estimates_overseas_stock_tax_only_for_selected_year_and_non_kr_market(self):
        estimate = estimate_overseas_capital_gains_tax(
            [
                OverseasRealizedTrade("AAPL", "US", date(2026, 3, 1), 5_000_000),
                OverseasRealizedTrade("MSFT", "US", date(2026, 4, 1), -500_000),
                OverseasRealizedTrade("005930", "KR", date(2026, 5, 1), 10_000_000),
                OverseasRealizedTrade("NVDA", "US", date(2025, 12, 1), 10_000_000),
            ],
            2026,
        )

        self.assertEqual(2, estimate.trade_count)
        self.assertEqual(4_500_000, estimate.net_gain_krw)
        self.assertEqual(2_000_000, estimate.taxable_gain_krw)
        self.assertEqual(440_000, estimate.estimated_tax_krw)

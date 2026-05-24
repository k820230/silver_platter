from datetime import datetime, timedelta
from unittest import TestCase

from silver_platter.data_quality import PriceBarInput
from silver_platter.history_risk import build_price_history_risk_chart


class HistoryRiskTests(TestCase):
    def test_build_price_history_risk_chart_returns_bounds_and_evidence(self):
        start = datetime(2026, 5, 1, 16, 0, 0)
        bars = [
            PriceBarInput(
                security_id="005930",
                bar_ts=start + timedelta(days=index),
                close_price=70000 + index * 350,
                volume=1000000 + index * 10000,
                turnover_krw=(70000 + index * 350) * (1000000 + index * 10000),
                available_to_model_at=start + timedelta(days=index),
            )
            for index in range(24)
        ]

        chart = build_price_history_risk_chart("005930", "KR", bars, "1w", limit=20)

        self.assertEqual("005930", chart["security_id"])
        self.assertEqual("1w", chart["risk_range"])
        self.assertEqual(20, chart["point_count"])
        self.assertEqual(20, len(chart["points"]))
        self.assertLess(chart["latest_risk"]["lower_bound"], chart["current_price"])
        self.assertGreater(chart["latest_risk"]["upper_bound"], chart["current_price"])
        self.assertIn("005930", chart["summary"])
        self.assertTrue(chart["evidence"])
        self.assertIn("가격 리스크", chart["reasoning"])

    def test_build_price_history_risk_chart_rejects_unknown_range(self):
        with self.assertRaises(ValueError):
            build_price_history_risk_chart("AAPL", "US", [], "2d")

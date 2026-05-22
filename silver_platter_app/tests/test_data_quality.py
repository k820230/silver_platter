import unittest
from datetime import datetime

from silver_platter.data_quality import PriceBarInput, RISK, evaluate_price_bars


class DataQualityTest(unittest.TestCase):
    def test_quality_blocks_missing_available_time(self):
        result = evaluate_price_bars(
            [
                PriceBarInput(
                    security_id="KR-005930",
                    bar_ts=datetime(2026, 1, 1),
                    close_price=70000,
                    volume=100,
                    turnover_krw=7000000,
                    available_to_model_at=None,
                )
            ]
        )
        self.assertEqual(result.status, RISK)
        self.assertIn(
            "MISSING_AVAILABLE_TO_MODEL_AT", [issue.code for issue in result.issues]
        )

    def test_quality_blocks_duplicate_bar(self):
        bar = PriceBarInput(
            security_id="KR-005930",
            bar_ts=datetime(2026, 1, 1),
            close_price=70000,
            volume=100,
            turnover_krw=7000000,
            available_to_model_at=datetime(2026, 1, 1),
        )
        result = evaluate_price_bars([bar, bar])
        self.assertEqual(result.status, RISK)


if __name__ == "__main__":
    unittest.main()

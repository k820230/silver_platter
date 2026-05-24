import unittest
from datetime import datetime

from silver_platter.data_quality import (
    CorporateActionAdjustment,
    PriceBarInput,
    RISK,
    apply_corporate_action_adjustments,
    calculate_average_turnover_krw,
    evaluate_price_bars,
)


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
        self.assertLess(result.score, 100)
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
        self.assertEqual(75, result.score)

    def test_calculates_average_turnover_for_latest_window(self):
        bars = [
            PriceBarInput(
                security_id="KR-005930",
                bar_ts=datetime(2026, 1, day),
                close_price=70000,
                volume=100,
                turnover_krw=float(day * 1000),
                available_to_model_at=datetime(2026, 1, day),
            )
            for day in [1, 2, 3]
        ]

        self.assertEqual(2500.0, calculate_average_turnover_krw(bars, window=2))

    def test_applies_corporate_action_adjustment_to_prior_bars(self):
        bars = [
            PriceBarInput(
                security_id="KR-005930",
                bar_ts=datetime(2026, 1, 1),
                close_price=100.0,
                volume=10.0,
                turnover_krw=1000.0,
                available_to_model_at=datetime(2026, 1, 1),
            ),
            PriceBarInput(
                security_id="KR-005930",
                bar_ts=datetime(2026, 1, 3),
                close_price=60.0,
                volume=20.0,
                turnover_krw=1200.0,
                available_to_model_at=datetime(2026, 1, 3),
            ),
        ]

        adjusted = apply_corporate_action_adjustments(
            bars,
            [
                CorporateActionAdjustment(
                    security_id="KR-005930",
                    effective_at=datetime(2026, 1, 2),
                    action_type="split",
                    price_multiplier=0.5,
                    volume_multiplier=2.0,
                )
            ],
        )

        self.assertEqual(50.0, adjusted[0].close_price)
        self.assertEqual(20.0, adjusted[0].volume)
        self.assertEqual(1000.0, adjusted[0].turnover_krw)
        self.assertEqual(60.0, adjusted[1].close_price)


if __name__ == "__main__":
    unittest.main()

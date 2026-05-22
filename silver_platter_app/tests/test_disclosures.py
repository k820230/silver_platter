from datetime import date
from unittest import TestCase

from silver_platter.disclosures import (
    DisclosureReaction,
    analyze_disclosure_impacts,
    predict_disclosure_impact,
)


class DisclosureTests(TestCase):
    def test_predicts_price_range_from_historical_reactions(self):
        pattern = analyze_disclosure_impacts(
            [
                DisclosureReaction("earnings", date(2026, 1, 1), 3, 0.04, 0.30),
                DisclosureReaction("earnings", date(2026, 2, 1), 5, -0.02, 0.10),
            ],
            "earnings",
        )
        prediction = predict_disclosure_impact(100.0, pattern)

        self.assertEqual(2, pattern.sample_count)
        self.assertEqual(98.0, prediction.expected_price_lower)
        self.assertEqual(104.0, prediction.expected_price_upper)

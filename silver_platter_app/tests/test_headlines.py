from datetime import datetime
from unittest import TestCase

from silver_platter.headlines import (
    EventMarketSnapshot,
    Headline,
    detect_geopolitical_market_alert,
    group_headlines_by_business_group,
    reliable_headlines,
)


class HeadlineTests(TestCase):
    def test_filters_to_trusted_providers(self):
        trusted = Headline(
            "LSEG",
            "Chip supply update",
            datetime(2026, 5, 22, 9, 0, 0),
            "https://example.com/a",
            group_ids=("semiconductor",),
        )
        untrusted = Headline(
            "random_blog",
            "Rumor",
            datetime(2026, 5, 22, 9, 1, 0),
            "https://example.com/b",
            group_ids=("semiconductor",),
        )

        self.assertEqual([trusted], reliable_headlines([trusted, untrusted]))
        grouped = group_headlines_by_business_group([trusted, untrusted])
        self.assertEqual([trusted], grouped["semiconductor"])

    def test_detects_geopolitical_volume_shock(self):
        alert = detect_geopolitical_market_alert(
            EventMarketSnapshot(
                event_id="e1",
                observed_at=datetime(2026, 5, 22, 10, 5, 0),
                event_tags=("geopolitical", "sanction"),
                five_min_avg_volume=2_100_000,
                previous_5d_five_min_avg_volume=1_000_000,
            )
        )

        self.assertIsNotNone(alert)
        self.assertEqual("warning", alert.severity)
        self.assertEqual(110.0, alert.volume_increase_pct)

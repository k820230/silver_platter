from datetime import datetime
from unittest import TestCase

from silver_platter.headlines import (
    EventMarketSnapshot,
    Headline,
    OfacRecentActionsHeadlineProvider,
    OfficialRssHeadlineProvider,
    OfficialRssSource,
    deduplicate_headlines,
    detect_geopolitical_market_alert,
    default_official_rss_sources,
    group_headlines_by_business_group,
    is_trusted_headline,
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

    def test_official_rss_provider_normalizes_rss_items_without_summary(self):
        def fetcher(url, headers):
            return """<?xml version="1.0"?>
            <rss version="2.0">
              <channel>
                <item>
                  <title>Federal Reserve issues policy statement</title>
                  <link>https://www.federalreserve.gov/newsevents/pressreleases/test.htm</link>
                  <guid>fed-guid-1</guid>
                  <pubDate>Fri, 22 May 2026 10:30:00 GMT</pubDate>
                  <description>Body text should not be stored.</description>
                </item>
              </channel>
            </rss>
            """

        provider = OfficialRssHeadlineProvider(
            OfficialRssSource(
                provider="federal_reserve",
                feed_url="https://www.federalreserve.gov/feeds/press_all.xml",
                event_tags=("central_bank",),
            ),
            fetcher=fetcher,
        )

        headlines = provider.fetch_headlines()

        self.assertEqual(1, len(headlines))
        self.assertEqual("federal_reserve", headlines[0].provider)
        self.assertEqual("Federal Reserve issues policy statement", headlines[0].title)
        self.assertEqual(datetime(2026, 5, 22, 10, 30, 0), headlines[0].published_at)
        self.assertEqual(("central_bank",), headlines[0].event_tags)
        self.assertEqual("fed-guid-1", headlines[0].metadata["raw_ref"])
        self.assertNotIn("description", headlines[0].metadata)

    def test_official_rss_provider_normalizes_atom_entries(self):
        def fetcher(url, headers):
            return """<?xml version="1.0"?>
            <feed xmlns="http://www.w3.org/2005/Atom">
              <entry>
                <title>ECB publishes market operation update</title>
                <link href="https://www.ecb.europa.eu/press/test.html" />
                <id>ecb-entry-1</id>
                <updated>2026-05-22T12:00:00Z</updated>
              </entry>
            </feed>
            """

        provider = OfficialRssHeadlineProvider(
            OfficialRssSource("ecb", "https://www.ecb.europa.eu/rss/press.html"),
            fetcher=fetcher,
        )

        headlines = provider.fetch_headlines(limit=1)

        self.assertTrue(is_trusted_headline(headlines[0]))
        self.assertEqual("ECB publishes market operation update", headlines[0].title)
        self.assertEqual("https://www.ecb.europa.eu/press/test.html", headlines[0].url)
        self.assertEqual(datetime(2026, 5, 22, 12, 0, 0), headlines[0].published_at)

    def test_default_official_rss_sources_include_fed_and_ecb(self):
        sources = default_official_rss_sources()

        self.assertEqual(["federal_reserve", "ecb"], [source.provider for source in sources])

    def test_deduplicates_headlines_by_normalized_title_and_day(self):
        first = Headline(
            "federal_reserve",
            "Federal Reserve issues policy statement",
            datetime(2026, 5, 22, 10, 0, 0),
            "https://www.federalreserve.gov/a",
        )
        second = Headline(
            "ecb",
            "Federal Reserve: issues policy statement!",
            datetime(2026, 5, 22, 10, 5, 0),
            "https://www.ecb.europa.eu/b",
        )

        clusters = deduplicate_headlines([first, second])

        self.assertEqual(1, len(clusters))
        self.assertEqual("ecb", clusters[0].representative.provider)
        self.assertEqual(2, clusters[0].provider_count)
        self.assertEqual(
            ("https://www.ecb.europa.eu/b", "https://www.federalreserve.gov/a"),
            clusters[0].source_urls,
        )
        self.assertNotIn("summary", clusters[0].as_dict()["representative"])

    def test_ofac_recent_actions_provider_normalizes_recent_action_rows(self):
        def fetcher(url, headers):
            return """
            <div class="view-content">
              <div class="margin-bottom-4 search-result views-row">
                <div><div><a href="/recent-actions/20260521">Counter Terrorism Designations</a></div></div>
                <div><div>May 21, 2026 -
                  <a href="/recent-actions/sanctions-list-updates">Sanctions List Updates</a>
                </div></div>
              </div>
            </div>
            """

        provider = OfacRecentActionsHeadlineProvider(fetcher=fetcher)

        headlines = provider.fetch_headlines()

        self.assertEqual(1, len(headlines))
        self.assertEqual("ofac", headlines[0].provider)
        self.assertEqual("Counter Terrorism Designations", headlines[0].title)
        self.assertEqual(datetime(2026, 5, 21, 0, 0, 0), headlines[0].published_at)
        self.assertIn("/recent-actions/20260521", headlines[0].url)
        self.assertEqual("Sanctions List Updates", headlines[0].metadata["category"])
        self.assertEqual(("geopolitical", "sanction"), headlines[0].event_tags)

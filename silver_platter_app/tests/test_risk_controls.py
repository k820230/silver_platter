from datetime import datetime, timedelta
from unittest import TestCase

from silver_platter.headlines import Headline, deduplicate_headlines
from silver_platter.risk_controls import (
    EventRiskSignal,
    KillSwitchInput,
    KillSwitchState,
    evaluate_event_risk,
    evaluate_kill_switch,
    headline_clusters_to_event_risk_signals,
)


class RiskControlsTests(TestCase):
    def test_kill_switch_blocks_security(self):
        issues = evaluate_kill_switch(
            KillSwitchState(blocked_securities={"AAPL"}),
            KillSwitchInput(account_id="a1", security_id="AAPL"),
        )

        self.assertEqual("KILL_SWITCH_SECURITY", issues[0].code)
        self.assertEqual("block", issues[0].severity)

    def test_event_risk_warns_for_active_group_signal(self):
        now = datetime(2026, 5, 22, 9, 0, 0)
        issues = evaluate_event_risk(
            [
                EventRiskSignal(
                    event_id="e1",
                    event_type="headline",
                    severity="warning",
                    observed_at=now,
                    group_ids={"semiconductor"},
                    expires_at=now + timedelta(minutes=30),
                )
            ],
            security_id="005930",
            group_ids={"semiconductor"},
            now=now,
        )

        self.assertEqual("warning", issues[0].severity)

    def test_event_risk_ignores_expired_signal(self):
        now = datetime(2026, 5, 22, 9, 0, 0)
        issues = evaluate_event_risk(
            [
                EventRiskSignal(
                    event_id="e1",
                    event_type="headline",
                    severity="critical",
                    observed_at=now - timedelta(hours=1),
                    security_ids={"AAPL"},
                    expires_at=now - timedelta(minutes=1),
                )
            ],
            security_id="AAPL",
            group_ids=set(),
            now=now,
        )

        self.assertEqual([], issues)

    def test_headline_clusters_convert_to_event_risk_signals(self):
        published_at = datetime(2026, 5, 22, 9, 0, 0)
        clusters = deduplicate_headlines(
            [
                Headline(
                    provider="federal_reserve",
                    title="Sanction shock affects chip exports",
                    published_at=published_at,
                    url="https://www.federalreserve.gov/a",
                    security_ids=("005930",),
                    group_ids=("semiconductor",),
                    event_tags=("geopolitical", "sanction"),
                )
            ]
        )

        signals = headline_clusters_to_event_risk_signals(clusters)

        self.assertEqual(1, len(signals))
        self.assertEqual("headline", signals[0].event_type)
        self.assertEqual("critical", signals[0].severity)
        self.assertEqual({"005930"}, signals[0].security_ids)
        self.assertEqual({"semiconductor"}, signals[0].group_ids)
        self.assertEqual(published_at + timedelta(minutes=30), signals[0].expires_at)

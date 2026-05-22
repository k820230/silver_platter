from datetime import datetime, timedelta
from unittest import TestCase

from silver_platter.risk_controls import (
    EventRiskSignal,
    KillSwitchInput,
    KillSwitchState,
    evaluate_event_risk,
    evaluate_kill_switch,
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

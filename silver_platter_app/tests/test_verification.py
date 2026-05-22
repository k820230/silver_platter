from datetime import datetime
from unittest import TestCase

from silver_platter.backtest import PaperReplayEvidence
from silver_platter.verification import (
    DEFAULT_GATE_REQUIREMENTS,
    GateEvidence,
    assess_gate,
    live_safety_to_gate_evidence,
    paper_replay_to_gate_evidence,
)


class VerificationTests(TestCase):
    def test_assess_gate_passes_when_all_evidence_passes(self):
        evidence = [
            GateEvidence("api_health", "pass", "curl /health", datetime(2026, 5, 22)),
            GateEvidence("web_health", "pass", "curl /", datetime(2026, 5, 22)),
            GateEvidence("compose_config", "pass", "docker-compose config", datetime(2026, 5, 22)),
        ]

        result = assess_gate("G2", DEFAULT_GATE_REQUIREMENTS, evidence)

        self.assertEqual("pass", result.status)
        self.assertEqual(3, result.passed_count)

    def test_assess_gate_blocks_when_evidence_missing(self):
        result = assess_gate("G4", DEFAULT_GATE_REQUIREMENTS, [])

        self.assertEqual("blocked", result.status)
        self.assertEqual(2, len(result.missing_requirements))

    def test_g6_paper_replay_evidence_can_pass_gate(self):
        replay = PaperReplayEvidence(
            run_id="bt-paper",
            status="pass",
            replay_day_count=10,
            order_count=3,
            accepted_order_count=3,
            blocked_order_count=0,
            lookahead_violation_count=0,
            broker_send_attempted=False,
            generated_at=datetime(2026, 5, 22, 9, 0, 0),
        )

        evidence = paper_replay_to_gate_evidence(replay, required_min_days=10)
        result = assess_gate("G6", DEFAULT_GATE_REQUIREMENTS, evidence)

        self.assertEqual("pass", result.status)
        self.assertEqual(3, result.passed_count)

    def test_g6_paper_replay_evidence_fails_on_broker_send(self):
        replay = PaperReplayEvidence(
            run_id="bt-paper",
            status="fail",
            replay_day_count=10,
            order_count=3,
            accepted_order_count=3,
            blocked_order_count=0,
            lookahead_violation_count=0,
            broker_send_attempted=True,
            generated_at=datetime(2026, 5, 22, 9, 0, 0),
        )

        evidence = paper_replay_to_gate_evidence(replay, required_min_days=10)
        result = assess_gate("G6", DEFAULT_GATE_REQUIREMENTS, evidence)

        self.assertEqual("blocked", result.status)
        self.assertEqual("paper_no_broker_send", result.failed_evidence[0].requirement_id)

    def test_g7_live_safety_evidence_can_pass_gate(self):
        evidence = live_safety_to_gate_evidence(
            live_order_enabled_default=False,
            kill_switch_tested=True,
            reconciliation_passed=True,
            checked_at=datetime(2026, 5, 22, 9, 0, 0),
        )

        result = assess_gate("G7", DEFAULT_GATE_REQUIREMENTS, evidence)

        self.assertEqual("pass", result.status)
        self.assertEqual(3, result.passed_count)

    def test_g7_live_safety_evidence_fails_when_live_default_enabled(self):
        evidence = live_safety_to_gate_evidence(
            live_order_enabled_default=True,
            kill_switch_tested=True,
            reconciliation_passed=True,
            checked_at=datetime(2026, 5, 22, 9, 0, 0),
        )

        result = assess_gate("G7", DEFAULT_GATE_REQUIREMENTS, evidence)

        self.assertEqual("blocked", result.status)
        self.assertEqual("live_order_disabled_default", result.failed_evidence[0].requirement_id)

from datetime import datetime
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from silver_platter.backtest import PaperReplayEvidence
from silver_platter.backup import BackupRestoreStatus
from silver_platter.verification import (
    DEFAULT_GATE_REQUIREMENTS,
    GateEvidence,
    assess_gate,
    backup_status_to_gate_evidence,
    build_verification_evidence_bundle,
    live_safety_to_gate_evidence,
    paper_replay_to_gate_evidence,
    script_result_to_gate_evidence,
    write_verification_evidence_bundle,
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

    def test_script_result_to_gate_evidence_maps_exit_code(self):
        checked_at = datetime(2026, 5, 22, 9, 0, 0)

        passed = script_result_to_gate_evidence(
            "api_health",
            "scripts/check",
            0,
            checked_at,
            output="ok",
        )
        failed = script_result_to_gate_evidence(
            "api_health",
            "scripts/smoke_api",
            1,
            checked_at,
            output="failure",
        )

        self.assertEqual("pass", passed.status)
        self.assertEqual("fail", failed.status)
        self.assertEqual("script:scripts/check", passed.evidence_uri)
        self.assertIn("exit_code=1", failed.detail)

    def test_verification_evidence_bundle_writes_assessments(self):
        checked_at = datetime(2026, 5, 22, 12, 0, 0)
        evidence = [
            GateEvidence("api_health", "pass", "GET /health", checked_at),
            GateEvidence("web_health", "pass", "GET /", checked_at),
            GateEvidence("compose_config", "pass", "docker compose config", checked_at),
        ]
        bundle = build_verification_evidence_bundle(
            evidence,
            gate_ids=("G2",),
            generated_at=checked_at,
        )

        with TemporaryDirectory() as tmp:
            path = write_verification_evidence_bundle(
                bundle,
                Path(tmp) / "evidence.json",
            )
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual("pass", bundle.assessments[0].status)
        self.assertEqual("G2", payload["assessments"][0]["gate_id"])
        self.assertEqual("compose_config", payload["evidence"][2]["requirement_id"])

    def test_backup_status_to_gate_evidence_passes_restorable_backup(self):
        checked_at = datetime(2026, 5, 22, 9, 0, 0)
        status = BackupRestoreStatus(
            status="ok",
            backup_base_dir="/backup",
            latest_manifest_path="/backup/2026-05-22/manifest.json",
            latest_backup_date="2026-05-22",
            backup_status="success",
            restore_status="ok",
            latest_restore_drill_path=None,
            restore_drill_status="missing",
            restore_drill_checked_at=None,
            lock_held=False,
            checked_at=checked_at,
            issue_count=0,
            issues=[],
        )

        evidence = backup_status_to_gate_evidence(status)
        assessment = assess_gate("G8", DEFAULT_GATE_REQUIREMENTS, [evidence])

        self.assertEqual("pass", evidence.status)
        self.assertEqual("pass", assessment.status)

    def test_backup_status_to_gate_evidence_fails_critical_backup(self):
        checked_at = datetime(2026, 5, 22, 9, 0, 0)
        status = BackupRestoreStatus(
            status="critical",
            backup_base_dir="/backup",
            latest_manifest_path="/backup/manifest.json",
            latest_backup_date=None,
            backup_status="unknown",
            restore_status="failed",
            latest_restore_drill_path=None,
            restore_drill_status="missing",
            restore_drill_checked_at=None,
            lock_held=False,
            checked_at=checked_at,
            issue_count=1,
            issues=["manifest is not valid json"],
        )

        evidence = backup_status_to_gate_evidence(status)

        self.assertEqual("fail", evidence.status)
        self.assertIn("manifest is not valid json", evidence.detail)

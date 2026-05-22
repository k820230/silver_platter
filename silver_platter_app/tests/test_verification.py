from datetime import datetime
from unittest import TestCase

from silver_platter.verification import (
    DEFAULT_GATE_REQUIREMENTS,
    GateEvidence,
    assess_gate,
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

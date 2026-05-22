from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class GateRequirement:
    gate_id: str
    requirement_id: str
    title: str
    evidence_hint: str


@dataclass(frozen=True)
class GateEvidence:
    requirement_id: str
    status: str
    evidence_uri: str
    checked_at: datetime
    detail: str = ""


@dataclass(frozen=True)
class GateAssessment:
    gate_id: str
    status: str
    passed_count: int
    total_count: int
    missing_requirements: Tuple[GateRequirement, ...] = field(default_factory=tuple)
    failed_evidence: Tuple[GateEvidence, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict:
        return {
            "gate_id": self.gate_id,
            "status": self.status,
            "passed_count": self.passed_count,
            "total_count": self.total_count,
            "missing_requirements": [item.__dict__ for item in self.missing_requirements],
            "failed_evidence": [
                {
                    "requirement_id": item.requirement_id,
                    "status": item.status,
                    "evidence_uri": item.evidence_uri,
                    "checked_at": item.checked_at.isoformat(),
                    "detail": item.detail,
                }
                for item in self.failed_evidence
            ],
        }


DEFAULT_GATE_REQUIREMENTS: Tuple[GateRequirement, ...] = (
    GateRequirement("G2", "api_health", "API health responds", "GET /health"),
    GateRequirement("G2", "web_health", "Web UI responds", "GET /"),
    GateRequirement("G2", "compose_config", "Compose config renders", "docker-compose config"),
    GateRequirement("G3", "price_quality", "Price bar quality passes", "POST /api/data/price-bars/quality"),
    GateRequirement("G4", "simulation_no_broker", "Simulation never sends broker order", "Paper adapter ack"),
    GateRequirement("G4", "fifo_pnl", "FIFO realized PnL is calculated", "tests/test_accounting_posting.py"),
    GateRequirement("G5", "backtest_no_lookahead", "Backtest blocks lookahead", "tests/test_backtest.py"),
    GateRequirement("G8", "backup_manifest", "Backup manifest is restorable", "tests/test_backup.py"),
)


def assess_gate(
    gate_id: str,
    requirements: Iterable[GateRequirement],
    evidence: Iterable[GateEvidence],
) -> GateAssessment:
    selected_requirements = [
        requirement for requirement in requirements if requirement.gate_id == gate_id
    ]
    evidence_by_requirement: Dict[str, GateEvidence] = {
        item.requirement_id: item for item in evidence
    }
    missing: List[GateRequirement] = []
    failed: List[GateEvidence] = []
    passed = 0
    for requirement in selected_requirements:
        item: Optional[GateEvidence] = evidence_by_requirement.get(
            requirement.requirement_id
        )
        if item is None:
            missing.append(requirement)
            continue
        if item.status != "pass":
            failed.append(item)
            continue
        passed += 1
    if missing or failed:
        status = "blocked"
    else:
        status = "pass"
    return GateAssessment(
        gate_id=gate_id,
        status=status,
        passed_count=passed,
        total_count=len(selected_requirements),
        missing_requirements=tuple(missing),
        failed_evidence=tuple(failed),
    )

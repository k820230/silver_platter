from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, List, Optional, Set

from silver_platter.risk import BLOCK, WARNING, RiskIssue


@dataclass(frozen=True)
class KillSwitchState:
    global_block: bool = False
    blocked_accounts: Set[str] = field(default_factory=set)
    blocked_strategies: Set[str] = field(default_factory=set)
    blocked_securities: Set[str] = field(default_factory=set)
    reason: str = ""


@dataclass(frozen=True)
class KillSwitchInput:
    account_id: str
    security_id: str
    strategy_id: Optional[str] = None


@dataclass(frozen=True)
class EventRiskSignal:
    event_id: str
    event_type: str
    severity: str
    observed_at: datetime
    security_ids: Set[str] = field(default_factory=set)
    group_ids: Set[str] = field(default_factory=set)
    expires_at: Optional[datetime] = None


def evaluate_kill_switch(
    state: KillSwitchState, risk_input: KillSwitchInput
) -> List[RiskIssue]:
    issues: List[RiskIssue] = []
    if state.global_block:
        issues.append(
            RiskIssue("KILL_SWITCH_GLOBAL", BLOCK, state.reason or "global kill switch is active")
        )
    if risk_input.account_id in state.blocked_accounts:
        issues.append(
            RiskIssue("KILL_SWITCH_ACCOUNT", BLOCK, "account kill switch is active")
        )
    if risk_input.security_id in state.blocked_securities:
        issues.append(
            RiskIssue("KILL_SWITCH_SECURITY", BLOCK, "security kill switch is active")
        )
    if risk_input.strategy_id and risk_input.strategy_id in state.blocked_strategies:
        issues.append(
            RiskIssue("KILL_SWITCH_STRATEGY", BLOCK, "strategy kill switch is active")
        )
    return issues


def evaluate_event_risk(
    signals: Iterable[EventRiskSignal],
    security_id: str,
    group_ids: Iterable[str],
    now: Optional[datetime] = None,
) -> List[RiskIssue]:
    current_time = now or datetime.utcnow()
    groups = set(group_ids)
    issues: List[RiskIssue] = []
    for signal in signals:
        if signal.expires_at is not None and signal.expires_at <= current_time:
            continue
        if security_id not in signal.security_ids and not groups.intersection(signal.group_ids):
            continue
        severity = BLOCK if signal.severity.strip().lower() in {"critical", "block"} else WARNING
        issues.append(
            RiskIssue(
                "EVENT_RISK_%s" % signal.event_type.strip().upper(),
                severity,
                "active event risk signal affects this order candidate",
            )
        )
    return issues

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Iterable, List, Optional, Set

from silver_platter.headlines import GEOPOLITICAL_TAGS, HeadlineDedupCluster
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


def headline_clusters_to_event_risk_signals(
    clusters: Iterable[HeadlineDedupCluster],
    expires_after: timedelta = timedelta(minutes=30),
) -> List[EventRiskSignal]:
    signals: List[EventRiskSignal] = []
    for cluster in clusters:
        tags = {
            tag.strip().lower()
            for headline in cluster.headlines
            for tag in headline.event_tags
            if tag.strip()
        }
        security_ids = {
            security_id
            for headline in cluster.headlines
            for security_id in headline.security_ids
        }
        group_ids = {
            group_id
            for headline in cluster.headlines
            for group_id in headline.group_ids
        }
        if not tags.intersection(GEOPOLITICAL_TAGS):
            continue
        severe_tags = {"sanction", "terror", "war"}
        severity = "critical" if tags.intersection(severe_tags) else "warning"
        observed_at = cluster.representative.published_at
        signals.append(
            EventRiskSignal(
                event_id=cluster.cluster_id,
                event_type="headline",
                severity=severity,
                observed_at=observed_at,
                security_ids=security_ids,
                group_ids=group_ids,
                expires_at=observed_at + expires_after,
            )
        )
    return signals

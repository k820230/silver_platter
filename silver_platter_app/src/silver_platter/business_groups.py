from dataclasses import dataclass, field
from datetime import date
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from silver_platter.risk import BLOCK, PASS, WARNING, MvpRiskLimits, RiskIssue


@dataclass(frozen=True)
class BusinessGroup:
    group_id: str
    name: str
    standard_industry_codes: Tuple[str, ...] = ()
    business_tags: Tuple[str, ...] = ()
    max_weight_warning: float = 0.20
    max_weight_block: float = 0.30
    max_loss_warning: float = -0.05
    max_loss_block: float = -0.08


@dataclass(frozen=True)
class SecurityBusinessProfile:
    security_id: str
    standard_industry_code: str
    business_tags: Tuple[str, ...] = ()
    manual_group_id: Optional[str] = None


@dataclass(frozen=True)
class GroupAssignment:
    security_id: str
    group_id: str
    confidence: float
    source: str
    matched_tags: Tuple[str, ...] = ()


@dataclass(frozen=True)
class GroupRiskDecision:
    group_id: str
    status: str
    issues: List[RiskIssue] = field(default_factory=list)
    group_weight: Optional[float] = None
    group_order_to_adv20: Optional[float] = None

    def as_dict(self) -> dict:
        return {
            "group_id": self.group_id,
            "status": self.status,
            "group_weight": self.group_weight,
            "group_order_to_adv20": self.group_order_to_adv20,
            "issues": [issue.__dict__ for issue in self.issues],
        }


@dataclass(frozen=True)
class VolatilityObservation:
    group_id: str
    observation_date: date
    volatility_value: float


@dataclass(frozen=True)
class GroupVolatilityPoint:
    group_id: str
    observation_date: date
    volatility_value: float
    change_pct_from_base: float


def _normalized_tags(tags: Iterable[str]) -> Tuple[str, ...]:
    return tuple(sorted({tag.strip().lower() for tag in tags if tag.strip()}))


def classify_security(
    profile: SecurityBusinessProfile, groups: Sequence[BusinessGroup]
) -> GroupAssignment:
    groups_by_id = {group.group_id: group for group in groups}
    if profile.manual_group_id and profile.manual_group_id in groups_by_id:
        return GroupAssignment(
            security_id=profile.security_id,
            group_id=profile.manual_group_id,
            confidence=1.0,
            source="manual",
        )

    security_tags = set(_normalized_tags(profile.business_tags))
    best_group: Optional[BusinessGroup] = None
    best_score = 0.0
    best_tags: Tuple[str, ...] = ()
    standard_code = profile.standard_industry_code.strip()

    for group in groups:
        score = 0.0
        for code in group.standard_industry_codes:
            normalized_code = code.strip()
            if standard_code == normalized_code:
                score += 3.0
            elif normalized_code and standard_code.startswith(normalized_code):
                score += 1.5
        group_tags = set(_normalized_tags(group.business_tags))
        matched_tags = tuple(sorted(security_tags.intersection(group_tags)))
        score += len(matched_tags)
        if score > best_score:
            best_group = group
            best_score = score
            best_tags = matched_tags

    if best_group is None:
        return GroupAssignment(
            security_id=profile.security_id,
            group_id="UNCLASSIFIED",
            confidence=0.0,
            source="unclassified",
        )

    confidence = min(1.0, best_score / 4.0)
    return GroupAssignment(
        security_id=profile.security_id,
        group_id=best_group.group_id,
        confidence=round(confidence, 4),
        source="standard_industry_and_similarity",
        matched_tags=best_tags,
    )


def evaluate_business_group_risk(
    group: BusinessGroup,
    group_exposure_krw: float,
    total_equity_krw: float,
    group_return_pct: float,
    group_day_new_order_amount_krw: Optional[float],
    group_avg_daily_turnover_20d_krw: Optional[float],
    limits: MvpRiskLimits = MvpRiskLimits(),
) -> GroupRiskDecision:
    issues: List[RiskIssue] = []
    group_weight: Optional[float] = None
    if total_equity_krw <= 0:
        issues.append(
            RiskIssue(
                "TOTAL_EQUITY_MISSING",
                BLOCK,
                "total equity must be positive to evaluate group concentration",
            )
        )
    else:
        group_weight = group_exposure_krw / total_equity_krw
        if group_weight > group.max_weight_block:
            issues.append(
                RiskIssue(
                    "GROUP_WEIGHT_BLOCK",
                    BLOCK,
                    "business group exposure is above the block threshold",
                    group_weight,
                    group.max_weight_block,
                )
            )
        elif group_weight > group.max_weight_warning:
            issues.append(
                RiskIssue(
                    "GROUP_WEIGHT_WARNING",
                    WARNING,
                    "business group exposure is above the warning threshold",
                    group_weight,
                    group.max_weight_warning,
                )
            )

    if group_return_pct <= group.max_loss_block:
        issues.append(
            RiskIssue(
                "GROUP_LOSS_BLOCK",
                BLOCK,
                "business group loss is above the block threshold",
                group_return_pct,
                group.max_loss_block,
            )
        )
    elif group_return_pct <= group.max_loss_warning:
        issues.append(
            RiskIssue(
                "GROUP_LOSS_WARNING",
                WARNING,
                "business group loss is above the warning threshold",
                group_return_pct,
                group.max_loss_warning,
            )
        )

    group_order_to_adv20: Optional[float] = None
    if group_day_new_order_amount_krw is not None or group_avg_daily_turnover_20d_krw is not None:
        if (
            group_day_new_order_amount_krw is None
            or group_avg_daily_turnover_20d_krw is None
            or group_avg_daily_turnover_20d_krw <= 0
        ):
            issues.append(
                RiskIssue(
                    "GROUP_LIQUIDITY_INPUT_MISSING",
                    BLOCK,
                    "group order amount and group ADV20 are required together",
                )
            )
        else:
            group_order_to_adv20 = (
                group_day_new_order_amount_krw / group_avg_daily_turnover_20d_krw
            )
            if group_order_to_adv20 > limits.group_order_to_adv20_limit:
                issues.append(
                    RiskIssue(
                        "GROUP_LIQUIDITY_LIMIT_EXCEEDED",
                        BLOCK,
                        "group daily new orders exceed the group liquidity limit",
                        group_order_to_adv20,
                        limits.group_order_to_adv20_limit,
                    )
                )

    status = BLOCK if any(issue.severity == BLOCK for issue in issues) else PASS
    if status == PASS and any(issue.severity == WARNING for issue in issues):
        status = WARNING
    return GroupRiskDecision(
        group_id=group.group_id,
        status=status,
        issues=issues,
        group_weight=None if group_weight is None else round(group_weight, 6),
        group_order_to_adv20=(
            None if group_order_to_adv20 is None else round(group_order_to_adv20, 6)
        ),
    )


def normalized_group_volatility_changes(
    observations: Iterable[VolatilityObservation], base_date: date
) -> Dict[str, List[GroupVolatilityPoint]]:
    by_group: Dict[str, List[VolatilityObservation]] = {}
    for observation in observations:
        if observation.volatility_value <= 0:
            continue
        by_group.setdefault(observation.group_id, []).append(observation)

    normalized: Dict[str, List[GroupVolatilityPoint]] = {}
    for group_id, group_observations in by_group.items():
        sorted_observations = sorted(
            group_observations, key=lambda item: item.observation_date
        )
        base_values = [
            item.volatility_value
            for item in sorted_observations
            if item.observation_date == base_date
        ]
        if not base_values:
            raise ValueError("base date volatility is missing for group %s" % group_id)
        base_value = base_values[-1]
        normalized[group_id] = [
            GroupVolatilityPoint(
                group_id=item.group_id,
                observation_date=item.observation_date,
                volatility_value=round(item.volatility_value, 6),
                change_pct_from_base=round(
                    (item.volatility_value / base_value - 1.0) * 100.0, 4
                ),
            )
            for item in sorted_observations
        ]
    return normalized

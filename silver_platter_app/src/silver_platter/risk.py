from dataclasses import dataclass, field
from typing import List, Optional


PASS = "pass"
WARNING = "warning"
BLOCK = "block"


@dataclass(frozen=True)
class MvpRiskLimits:
    min_security_investment_krw: int = 100_000
    max_security_investment_krw: int = 1_000_000_000
    max_auto_order_amount_krw: int = 1_000_000_000
    order_to_adv20_limit: float = 0.05
    group_order_to_adv20_limit: float = 0.05
    low_liquidity_adv20_floor_krw: int = 1_000_000_000
    low_liquidity_slippage_multiplier: float = 3.0
    kr_market_slippage_bps: float = 10.0
    kr_limit_slippage_bps: float = 5.0
    us_market_slippage_bps: float = 8.0
    us_limit_slippage_bps: float = 4.0


@dataclass(frozen=True)
class RiskIssue:
    code: str
    severity: str
    message: str
    value: Optional[float] = None
    limit: Optional[float] = None


@dataclass(frozen=True)
class RiskDecision:
    status: str
    issues: List[RiskIssue] = field(default_factory=list)
    applied_slippage_bps: float = 0.0
    low_liquidity_multiplier: float = 1.0

    @property
    def blocked(self) -> bool:
        return self.status == BLOCK

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "applied_slippage_bps": self.applied_slippage_bps,
            "low_liquidity_multiplier": self.low_liquidity_multiplier,
            "issues": [issue.__dict__ for issue in self.issues],
        }


@dataclass(frozen=True)
class OrderRiskInput:
    order_amount_krw: float
    avg_daily_turnover_20d_krw: Optional[float]
    market: str
    order_type: str
    is_auto_order: bool = False
    group_day_new_order_amount_krw: Optional[float] = None
    group_avg_daily_turnover_20d_krw: Optional[float] = None


def _base_slippage_bps(market: str, order_type: str, limits: MvpRiskLimits) -> float:
    market_normalized = market.strip().upper()
    order_type_normalized = order_type.strip().lower()
    if market_normalized in {"KR", "KRX", "KOSPI", "KOSDAQ"}:
        return (
            limits.kr_limit_slippage_bps
            if order_type_normalized == "limit"
            else limits.kr_market_slippage_bps
        )
    return (
        limits.us_limit_slippage_bps
        if order_type_normalized == "limit"
        else limits.us_market_slippage_bps
    )


def evaluate_order_risk(
    risk_input: OrderRiskInput, limits: MvpRiskLimits = MvpRiskLimits()
) -> RiskDecision:
    issues: List[RiskIssue] = []
    amount = risk_input.order_amount_krw

    if amount < limits.min_security_investment_krw:
        issues.append(
            RiskIssue(
                "AMOUNT_BELOW_MIN",
                BLOCK,
                "order amount is below the minimum single-security investment",
                amount,
                limits.min_security_investment_krw,
            )
        )
    if amount > limits.max_security_investment_krw:
        issues.append(
            RiskIssue(
                "AMOUNT_ABOVE_MAX",
                BLOCK,
                "order amount is above the maximum single-security investment",
                amount,
                limits.max_security_investment_krw,
            )
        )
    if risk_input.is_auto_order and amount > limits.max_auto_order_amount_krw:
        issues.append(
            RiskIssue(
                "AUTO_ORDER_AMOUNT_ABOVE_MAX",
                BLOCK,
                "auto order amount is above the maximum per-order limit",
                amount,
                limits.max_auto_order_amount_krw,
            )
        )

    adv20 = risk_input.avg_daily_turnover_20d_krw
    low_liquidity_multiplier = 1.0
    if adv20 is None or adv20 <= 0:
        issues.append(
            RiskIssue(
                "ADV20_MISSING",
                BLOCK,
                "20-trading-day average turnover is required for liquidity gate",
            )
        )
    else:
        order_to_adv20 = amount / adv20
        if order_to_adv20 > limits.order_to_adv20_limit:
            issues.append(
                RiskIssue(
                    "LIQUIDITY_LIMIT_EXCEEDED",
                    BLOCK,
                    "order amount exceeds 5% of 20-trading-day average turnover",
                    order_to_adv20,
                    limits.order_to_adv20_limit,
                )
            )
        if adv20 < limits.low_liquidity_adv20_floor_krw:
            low_liquidity_multiplier = limits.low_liquidity_slippage_multiplier
            issues.append(
                RiskIssue(
                    "LOW_LIQUIDITY_SLIPPAGE_MULTIPLIER",
                    WARNING,
                    "low liquidity security uses 3x base slippage",
                    adv20,
                    limits.low_liquidity_adv20_floor_krw,
                )
            )

    group_amount = risk_input.group_day_new_order_amount_krw
    group_adv20 = risk_input.group_avg_daily_turnover_20d_krw
    if group_amount is not None or group_adv20 is not None:
        if group_amount is None or group_adv20 is None or group_adv20 <= 0:
            issues.append(
                RiskIssue(
                    "GROUP_LIQUIDITY_INPUT_MISSING",
                    BLOCK,
                    "group daily order amount and group ADV20 are required together",
                )
            )
        else:
            group_ratio = group_amount / group_adv20
            if group_ratio > limits.group_order_to_adv20_limit:
                issues.append(
                    RiskIssue(
                        "GROUP_LIQUIDITY_LIMIT_EXCEEDED",
                        BLOCK,
                        "group daily new orders exceed 5% of group ADV20",
                        group_ratio,
                        limits.group_order_to_adv20_limit,
                    )
                )

    base_slippage = _base_slippage_bps(
        risk_input.market, risk_input.order_type, limits
    )
    applied_slippage = base_slippage * low_liquidity_multiplier
    status = BLOCK if any(issue.severity == BLOCK for issue in issues) else PASS
    if status == PASS and any(issue.severity == WARNING for issue in issues):
        status = WARNING
    return RiskDecision(
        status=status,
        issues=issues,
        applied_slippage_bps=applied_slippage,
        low_liquidity_multiplier=low_liquidity_multiplier,
    )

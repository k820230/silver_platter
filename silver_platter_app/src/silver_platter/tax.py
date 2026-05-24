from dataclasses import dataclass
from datetime import date
from typing import Iterable, List


@dataclass(frozen=True)
class OverseasRealizedTrade:
    security_id: str
    market: str
    realized_date: date
    realized_pnl_krw: float
    fee_krw: float = 0.0


@dataclass(frozen=True)
class OverseasCapitalGainsTaxEstimate:
    tax_year: int
    trade_count: int
    gross_gain_krw: float
    gross_loss_krw: float
    net_gain_krw: float
    basic_deduction_krw: float
    taxable_gain_krw: float
    national_income_tax_krw: float
    local_income_tax_krw: float
    estimated_tax_krw: float
    report_type: str = "simple_supporting_estimate"

    def as_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass(frozen=True)
class TaxEstimateComparison:
    tax_year: int
    preview_estimated_tax_krw: float
    actual_estimated_tax_krw: float
    delta_krw: float
    delta_pct: float

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def estimate_overseas_capital_gains_tax(
    trades: Iterable[OverseasRealizedTrade],
    tax_year: int,
    basic_deduction_krw: float = 2_500_000.0,
    national_tax_rate: float = 0.20,
    local_income_tax_rate: float = 0.02,
) -> OverseasCapitalGainsTaxEstimate:
    selected: List[OverseasRealizedTrade] = [
        trade
        for trade in trades
        if trade.realized_date.year == tax_year and trade.market.strip().upper() != "KR"
    ]
    gross_gain = sum(max(0.0, trade.realized_pnl_krw) for trade in selected)
    gross_loss = sum(min(0.0, trade.realized_pnl_krw) for trade in selected)
    net_gain = gross_gain + gross_loss
    taxable_gain = max(0.0, net_gain - basic_deduction_krw)
    national_tax = taxable_gain * national_tax_rate
    local_tax = taxable_gain * local_income_tax_rate
    estimated_tax = national_tax + local_tax
    return OverseasCapitalGainsTaxEstimate(
        tax_year=tax_year,
        trade_count=len(selected),
        gross_gain_krw=round(gross_gain, 2),
        gross_loss_krw=round(gross_loss, 2),
        net_gain_krw=round(net_gain, 2),
        basic_deduction_krw=round(basic_deduction_krw, 2),
        taxable_gain_krw=round(taxable_gain, 2),
        national_income_tax_krw=round(national_tax, 2),
        local_income_tax_krw=round(local_tax, 2),
        estimated_tax_krw=round(estimated_tax, 2),
    )


def compare_tax_preview_to_actual(
    preview: OverseasCapitalGainsTaxEstimate,
    actual: OverseasCapitalGainsTaxEstimate,
) -> TaxEstimateComparison:
    if preview.tax_year != actual.tax_year:
        raise ValueError("tax estimate comparison requires the same tax_year")
    delta = actual.estimated_tax_krw - preview.estimated_tax_krw
    return TaxEstimateComparison(
        tax_year=preview.tax_year,
        preview_estimated_tax_krw=preview.estimated_tax_krw,
        actual_estimated_tax_krw=actual.estimated_tax_krw,
        delta_krw=round(delta, 2),
        delta_pct=(
            0.0
            if preview.estimated_tax_krw == 0
            else round(delta / preview.estimated_tax_krw, 6)
        ),
    )

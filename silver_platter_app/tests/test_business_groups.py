from datetime import date
from unittest import TestCase

from silver_platter.business_groups import (
    BusinessGroup,
    CurrencyPositionExposure,
    SecurityBusinessProfile,
    VolatilityObservation,
    calculate_currency_exposures,
    classify_security,
    evaluate_business_group_risk,
    normalized_group_volatility_changes,
)


class BusinessGroupTests(TestCase):
    def test_manual_group_assignment_wins(self):
        assignment = classify_security(
            SecurityBusinessProfile(
                "005930.KS",
                "2611",
                ("memory",),
                manual_group_id="semiconductor_memory",
            ),
            [
                BusinessGroup(
                    "semiconductor_memory",
                    "Semiconductor Memory",
                    ("2611",),
                    ("memory", "dram"),
                )
            ],
        )

        self.assertEqual("semiconductor_memory", assignment.group_id)
        self.assertEqual("manual", assignment.source)
        self.assertEqual(1.0, assignment.confidence)

    def test_group_risk_blocks_liquidity(self):
        decision = evaluate_business_group_risk(
            BusinessGroup("ev_battery", "EV Battery"),
            group_exposure_krw=100_000_000,
            total_equity_krw=1_000_000_000,
            group_return_pct=-0.01,
            group_day_new_order_amount_krw=60_000_000,
            group_avg_daily_turnover_20d_krw=1_000_000_000,
        )

        self.assertEqual("block", decision.status)
        self.assertEqual("GROUP_LIQUIDITY_LIMIT_EXCEEDED", decision.issues[0].code)

    def test_normalized_volatility_uses_selected_base_date(self):
        values = normalized_group_volatility_changes(
            [
                VolatilityObservation("g1", date(2026, 5, 20), 20.0),
                VolatilityObservation("g1", date(2026, 5, 21), 22.0),
                VolatilityObservation("g2", date(2026, 5, 20), 30.0),
                VolatilityObservation("g2", date(2026, 5, 21), 27.0),
            ],
            date(2026, 5, 20),
        )

        self.assertEqual(10.0, values["g1"][1].change_pct_from_base)
        self.assertEqual(-10.0, values["g2"][1].change_pct_from_base)

    def test_calculates_currency_exposure_weights(self):
        exposures = calculate_currency_exposures(
            [
                CurrencyPositionExposure("005930.KS", "KRW", 1_000_000),
                CurrencyPositionExposure("AAPL", "USD", 2_000_000),
                CurrencyPositionExposure("MSFT", "usd", 1_000_000),
            ],
            total_equity_krw=4_000_000,
        )

        by_currency = {item.currency: item for item in exposures}
        self.assertEqual(1_000_000, by_currency["KRW"].exposure_krw)
        self.assertEqual(3_000_000, by_currency["USD"].exposure_krw)
        self.assertEqual(0.75, by_currency["USD"].weight)

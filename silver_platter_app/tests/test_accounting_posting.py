from datetime import date
from unittest import TestCase

from silver_platter.accounting import (
    ExecutionPosting,
    ReconciliationInput,
    post_execution_fifo,
    reconcile_position_and_cash,
)


class AccountingPostingTests(TestCase):
    def test_post_buy_creates_transaction_cash_and_lot(self):
        result = post_execution_fifo(
            ExecutionPosting(
                transaction_id="tx-1",
                account_id="a1",
                security_id="AAPL",
                side="buy",
                quantity=10,
                unit_price_krw=1000,
                trade_date=date(2026, 5, 22),
                fee_krw=10,
            ),
            [],
        )

        self.assertEqual(-10010, result.cash_entry.amount_krw)
        self.assertIsNotNone(result.created_lot)
        self.assertEqual("buy", result.transaction_entry.side)

    def test_post_sell_matches_fifo_and_realizes_pnl(self):
        buy = post_execution_fifo(
            ExecutionPosting(
                "tx-buy",
                "a1",
                "AAPL",
                "buy",
                10,
                1000,
                date(2026, 5, 1),
            ),
            [],
        )
        sell = post_execution_fifo(
            ExecutionPosting(
                "tx-sell",
                "a1",
                "AAPL",
                "sell",
                4,
                1200,
                date(2026, 5, 22),
                fee_krw=8,
            ),
            [buy.created_lot],
        )

        self.assertEqual(792, sell.realized_pnl_krw)
        self.assertEqual(6, buy.created_lot.remaining_quantity)
        self.assertEqual(1, len(sell.fifo_matches))

    def test_reconciliation_reports_mismatch(self):
        report = reconcile_position_and_cash(
            ReconciliationInput(
                security_id="AAPL",
                broker_quantity=10,
                internal_quantity=11,
                broker_cash_krw=1000,
                internal_cash_krw=990,
            )
        )

        self.assertEqual("mismatch", report.status)
        self.assertEqual(2, len(report.issues))

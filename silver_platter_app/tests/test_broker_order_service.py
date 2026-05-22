from unittest import TestCase

from silver_platter.broker import KoreaInvestmentBrokerAdapter, PaperBrokerAdapter
from silver_platter.order_service import OrderSubmissionInput, OrderSubmissionService


class BrokerOrderServiceTests(TestCase):
    def test_paper_adapter_never_attempts_live_broker_send(self):
        service = OrderSubmissionService(PaperBrokerAdapter())
        result = service.submit(
            OrderSubmissionInput(
                order_id="o1",
                account_id="a1",
                security_id="AAPL",
                side="buy",
                order_type="limit",
                market="US",
                current_price=10000,
                quantity=20,
                avg_daily_turnover_20d_krw=100_000_000,
                idempotency_key="k1",
                limit_price=10000,
            )
        )

        self.assertTrue(result.accepted)
        self.assertEqual("accepted", result.state.state)
        self.assertEqual("paper-o1", result.broker_order_id)

    def test_kis_adapter_rejects_when_live_disabled(self):
        service = OrderSubmissionService(KoreaInvestmentBrokerAdapter(live_order_enabled=False))
        result = service.submit(
            OrderSubmissionInput(
                order_id="o2",
                account_id="a1",
                security_id="AAPL",
                side="buy",
                order_type="limit",
                market="US",
                current_price=10000,
                quantity=20,
                avg_daily_turnover_20d_krw=100_000_000,
                idempotency_key="k2",
            )
        )

        self.assertFalse(result.accepted)
        self.assertEqual("rejected", result.state.state)

    def test_submission_blocks_duplicate_idempotency_key(self):
        service = OrderSubmissionService(PaperBrokerAdapter())
        request = OrderSubmissionInput(
            order_id="o1",
            account_id="a1",
            security_id="AAPL",
            side="buy",
            order_type="limit",
            market="US",
            current_price=10000,
            quantity=20,
            avg_daily_turnover_20d_krw=100_000_000,
            idempotency_key="dup",
        )
        service.submit(request)
        duplicate = service.submit(
            OrderSubmissionInput(
                order_id="o2",
                account_id="a1",
                security_id="AAPL",
                side="buy",
                order_type="limit",
                market="US",
                current_price=10000,
                quantity=20,
                avg_daily_turnover_20d_krw=100_000_000,
                idempotency_key="dup",
            )
        )

        self.assertFalse(duplicate.accepted)
        self.assertEqual("duplicate idempotency key", duplicate.reason)

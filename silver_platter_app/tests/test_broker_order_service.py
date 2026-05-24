import json
from unittest import TestCase
from unittest.mock import patch

from silver_platter.broker import (
    BrokerOrderRequest,
    KoreaInvestmentBrokerAdapter,
    KoreaInvestmentCredentials,
    KoreaInvestmentHttpTransport,
    PaperBrokerAdapter,
    is_regular_order_time,
)
from silver_platter.order_service import OrderSubmissionInput, OrderSubmissionService


class FakeKisTransport:
    def __init__(self):
        self.calls = []

    def post(self, path, headers, body):
        self.calls.append((path, headers, body))
        if path == "/oauth2/tokenP":
            return {"access_token": "token-1"}
        return {
            "rt_cd": "0",
            "msg1": "order accepted",
            "output": {
                "KRX_FWDG_ORD_ORGNO": "001",
                "ODNO": "12345",
            },
        }

    def get(self, path, headers, params):
        self.calls.append((path, headers, params))
        return {
            "rt_cd": "0",
            "output": {
                "nrcvb_buy_amt": "5000000",
                "nrcvb_buy_qty": "71",
                "max_buy_amt": "6000000",
                "max_buy_qty": "85",
            },
        }


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

    def test_kis_adapter_requires_credentials_and_transport_for_live_mode(self):
        adapter = KoreaInvestmentBrokerAdapter(live_order_enabled=True)

        ack = adapter.submit_order(
            BrokerOrderRequest(
                order_id="o3",
                account_id="a1",
                security_id="005930",
                side="buy",
                order_type="limit",
                market="KR",
                quantity=10,
                limit_price=70000,
            )
        )

        self.assertFalse(ack.accepted)
        self.assertFalse(ack.broker_send_attempted)

    def test_kis_adapter_maps_live_domestic_cash_order_payload(self):
        transport = FakeKisTransport()
        adapter = KoreaInvestmentBrokerAdapter(
            live_order_enabled=True,
            credentials=KoreaInvestmentCredentials(
                app_key="app",
                app_secret="secret",
                account_number="12345678",
                account_product_code="01",
                trading_env="real",
            ),
            transport=transport,
        )

        ack = adapter.submit_order(
            BrokerOrderRequest(
                order_id="o4",
                account_id="a1",
                security_id="005930",
                side="buy",
                order_type="limit",
                market="KR",
                quantity=10,
                limit_price=70000,
            )
        )

        self.assertTrue(ack.accepted)
        self.assertTrue(ack.broker_send_attempted)
        self.assertEqual("001-12345", ack.broker_order_id)
        self.assertEqual("/oauth2/tokenP", transport.calls[0][0])
        self.assertEqual("/uapi/domestic-stock/v1/trading/order-cash", transport.calls[1][0])
        self.assertEqual("TTTC0012U", transport.calls[1][1]["tr_id"])
        self.assertEqual("Bearer token-1", transport.calls[1][1]["authorization"])
        self.assertEqual(
            {
                "CANO": "12345678",
                "ACNT_PRDT_CD": "01",
                "PDNO": "005930",
                "ORD_DVSN": "00",
                "ORD_QTY": "10",
                "ORD_UNPR": "70000",
                "EXCG_ID_DVSN_CD": "KRX",
                "SLL_TYPE": "",
                "CNDT_PRIC": "",
            },
            transport.calls[1][2],
        )

    def test_kis_adapter_defaults_to_demo_tr_ids(self):
        transport = FakeKisTransport()
        adapter = KoreaInvestmentBrokerAdapter(
            live_order_enabled=True,
            credentials=KoreaInvestmentCredentials("app", "secret", "12345678"),
            transport=transport,
        )

        ack = adapter.submit_order(
            BrokerOrderRequest(
                order_id="o-demo",
                account_id="a1",
                security_id="005930",
                side="sell",
                order_type="market",
                market="KR",
                quantity=1,
                limit_price=0,
            )
        )

        self.assertTrue(ack.accepted)
        self.assertEqual("VTTC0011U", transport.calls[1][1]["tr_id"])
        self.assertEqual("01", transport.calls[1][2]["ORD_DVSN"])

    def test_kis_adapter_maps_orderable_query(self):
        transport = FakeKisTransport()
        adapter = KoreaInvestmentBrokerAdapter(
            credentials=KoreaInvestmentCredentials(
                "app",
                "secret",
                "12345678",
                trading_env="demo",
            ),
            transport=transport,
        )

        result = adapter.inquire_domestic_orderable(
            "005930",
            order_price=70000,
            order_type="market",
        )

        self.assertEqual(5_000_000, result.nrcvb_buy_amount_krw)
        self.assertEqual(71, result.nrcvb_buy_quantity)
        self.assertEqual("VTTC8908R", transport.calls[1][1]["tr_id"])
        self.assertEqual("/uapi/domestic-stock/v1/trading/inquire-psbl-order", transport.calls[1][0])
        self.assertEqual(
            {
                "CANO": "12345678",
                "ACNT_PRDT_CD": "01",
                "PDNO": "005930",
                "ORD_UNPR": "70000",
                "ORD_DVSN": "01",
                "CMA_EVLU_AMT_ICLD_YN": "N",
                "OVRS_ICLD_YN": "N",
            },
            transport.calls[1][2],
        )

    def test_kis_adapter_rejects_unsupported_market_before_send(self):
        transport = FakeKisTransport()
        adapter = KoreaInvestmentBrokerAdapter(
            live_order_enabled=True,
            credentials=KoreaInvestmentCredentials("app", "secret", "12345678"),
            transport=transport,
        )

        ack = adapter.submit_order(
            BrokerOrderRequest(
                order_id="o5",
                account_id="a1",
                security_id="AAPL",
                side="buy",
                order_type="limit",
                market="US",
                quantity=10,
                limit_price=100,
            )
        )

        self.assertFalse(ack.accepted)
        self.assertFalse(ack.broker_send_attempted)
        self.assertEqual([], transport.calls)

    def test_kis_http_transport_posts_json(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return b'{"ok": true}'

        requests = []

        def fake_urlopen(request, timeout):
            requests.append((request, timeout))
            return FakeResponse()

        with patch("silver_platter.broker.urllib.request.urlopen", fake_urlopen):
            response = KoreaInvestmentHttpTransport("https://example.test").post(
                "/oauth2/tokenP",
                {"content-type": "application/json"},
                {"appkey": "app"},
            )

        self.assertTrue(response["ok"])
        self.assertEqual("POST", requests[0][0].get_method())
        self.assertEqual("https://example.test/oauth2/tokenP", requests[0][0].full_url)
        self.assertEqual({"appkey": "app"}, json.loads(requests[0][0].data.decode("utf-8")))

    def test_regular_order_time_checks_market_windows(self):
        from datetime import datetime

        self.assertTrue(is_regular_order_time("KR", datetime(2026, 5, 22, 10, 0, 0)))
        self.assertFalse(is_regular_order_time("KR", datetime(2026, 5, 22, 16, 0, 0)))
        self.assertTrue(is_regular_order_time("US", datetime(2026, 5, 22, 10, 0, 0)))
        self.assertFalse(is_regular_order_time("US", datetime(2026, 5, 23, 10, 0, 0)))

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

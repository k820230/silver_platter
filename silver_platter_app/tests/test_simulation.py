import unittest
from datetime import date

from silver_platter.simulation import SimulationEngine, VirtualAccount


class SimulationTest(unittest.TestCase):
    def test_simulation_buy_and_sell_updates_fifo_pnl(self):
        account = VirtualAccount("sim-1", cash_krw=10_000_000)
        engine = SimulationEngine(account)

        buy = engine.execute(
            security_id="KR-005930",
            side="buy",
            market="KR",
            order_type="limit",
            price=50_000,
            quantity=10,
            avg_daily_turnover_20d_krw=100_000_000_000,
            trade_date=date(2026, 1, 1),
        )
        self.assertTrue(buy.accepted)
        self.assertEqual(len(account.lots), 1)

        sell = engine.execute(
            security_id="KR-005930",
            side="sell",
            market="KR",
            order_type="limit",
            price=60_000,
            quantity=4,
            avg_daily_turnover_20d_krw=100_000_000_000,
            trade_date=date(2026, 1, 10),
        )
        self.assertTrue(sell.accepted)
        self.assertEqual(account.lots[0].remaining_quantity, 6)
        self.assertGreater(sell.realized_pnl_krw, 0)

    def test_simulation_rejects_risk_block(self):
        account = VirtualAccount("sim-1", cash_krw=10_000_000)
        engine = SimulationEngine(account)
        result = engine.execute(
            security_id="KR-LOW",
            side="buy",
            market="KR",
            order_type="market",
            price=50_000,
            quantity=100,
            avg_daily_turnover_20d_krw=10_000_000,
            trade_date=date(2026, 1, 1),
        )
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, "risk_block")


if __name__ == "__main__":
    unittest.main()

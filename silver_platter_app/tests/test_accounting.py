import unittest
from datetime import date

from silver_platter.accounting import BuyExecution, SellExecution, create_lot, match_sell_fifo


class AccountingTest(unittest.TestCase):
    def test_fifo_matches_oldest_lot_first(self):
        lot1 = create_lot(
            BuyExecution("b1", "KR-005930", 10, 50_000, date(2026, 1, 1))
        )
        lot2 = create_lot(
            BuyExecution("b2", "KR-005930", 10, 60_000, date(2026, 2, 1))
        )
        matches, realized = match_sell_fifo(
            SellExecution("s1", "KR-005930", 12, 70_000, date(2026, 3, 1), fee_krw=120),
            [lot2, lot1],
        )
        self.assertEqual([match.lot_id for match in matches], ["lot-b1", "lot-b2"])
        self.assertEqual(lot1.remaining_quantity, 0)
        self.assertEqual(lot2.remaining_quantity, 8)
        self.assertEqual(realized, 219_880.0)

    def test_fifo_rejects_oversell(self):
        lot = create_lot(
            BuyExecution("b1", "KR-005930", 1, 50_000, date(2026, 1, 1))
        )
        with self.assertRaises(ValueError):
            match_sell_fifo(
                SellExecution("s1", "KR-005930", 2, 70_000, date(2026, 3, 1)),
                [lot],
            )


if __name__ == "__main__":
    unittest.main()

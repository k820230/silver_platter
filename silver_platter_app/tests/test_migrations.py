import unittest

from silver_platter.migrations import list_migrations, render_migrations


class MigrationTest(unittest.TestCase):
    def test_expected_migrations_exist(self):
        names = [path.name for path in list_migrations()]
        self.assertIn("001_provider_security_market_data.sql", names)
        self.assertIn("002_account_fifo.sql", names)
        self.assertIn("003_risk_order_backup.sql", names)
        self.assertIn("004_seed_policy.sql", names)
        self.assertIn("006_order_controls_audit.sql", names)
        self.assertIn("007_ml_watchlist_performance.sql", names)
        self.assertIn("008_backtest_restore_operations.sql", names)

    def test_seed_contains_mvp_limits(self):
        rendered = render_migrations(list_migrations())
        self.assertIn("order_to_adv20", rendered)
        self.assertIn("weekly_goldilocks_full_backup", rendered)
        self.assertIn("korea_investment", rendered)
        self.assertIn("kill_switch_state", rendered)
        self.assertIn("order_state_event", rendered)
        self.assertIn("user_watchlist", rendered)
        self.assertIn("ml_prediction_actual", rendered)
        self.assertIn("backtest_run", rendered)
        self.assertIn("restore_check_run", rendered)


if __name__ == "__main__":
    unittest.main()

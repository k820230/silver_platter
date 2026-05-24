import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from silver_platter.migrations import (
    apply_migrations,
    build_migration_plan,
    goldilocks_compatible_statement,
    is_idempotent_create_statement,
    load_applied_migrations,
    list_migrations,
    render_migrations,
    sql_literal,
    split_sql_statements,
)
from silver_platter.providers import default_mvp_provider_catalog


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rows = []

    def execute(self, sql, params=None):
        if sql.startswith("SELECT migration_name"):
            if not self.connection.note_table_exists:
                raise RuntimeError("schema_migration_note is missing")
            self.rows = list(self.connection.applied.items())
            return self

        if sql.startswith("INSERT INTO SP.schema_migration_note"):
            self.connection.note_table_exists = True
            values = sql.split("VALUES", 1)[1]
            name, checksum = [
                item.strip().strip("'")
                for item in values.strip().lstrip("(").rstrip(")").split(",")
            ]
            self.connection.applied[name] = checksum
            return self

        self.connection.statements.append(sql)
        if "schema_migration_note" in sql:
            self.connection.note_table_exists = True
        return self

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self):
        self.applied = {}
        self.commits = 0
        self.note_table_exists = False
        self.rollbacks = 0
        self.statements = []

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class BrokenCursor:
    def execute(self, sql, params=None):
        raise RuntimeError("permission denied")


class BrokenConnection:
    def cursor(self):
        return BrokenCursor()


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
        self.assertIn("009_verification_alert_evidence.sql", names)
        self.assertIn("010_headline_event_pipeline.sql", names)
        self.assertIn("011_provider_catalog_license_seed.sql", names)

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
        self.assertIn("verification_gate_assessment", rendered)
        self.assertIn("alert_delivery_run", rendered)
        self.assertIn("headline_event", rendered)
        self.assertIn("headline_risk_signal", rendered)
        self.assertIn("federal_reserve", rendered)
        self.assertIn("free_fx_placeholder", rendered)
        self.assertIn("data_license", rendered)

    def test_rendered_seed_covers_default_provider_catalog(self):
        rendered = render_migrations(list_migrations())

        for provider in default_mvp_provider_catalog():
            self.assertIn(provider.provider_code, rendered)

    def test_split_sql_statements_respects_strings_and_comments(self):
        statements = split_sql_statements(
            """
            -- comment with ;
            CREATE TABLE sample_note (body VARCHAR(64));
            INSERT INTO sample_note VALUES ('semi;colon');
            /* block ; comment */
            INSERT INTO sample_note VALUES ('single '' quote');
            """
        )

        self.assertEqual(3, len(statements))
        self.assertIn("'semi;colon'", statements[1])

    def test_goldilocks_compatible_statement_removes_unsupported_if_not_exists(self):
        self.assertEqual(
            "CREATE SCHEMA SP",
            goldilocks_compatible_statement("CREATE SCHEMA IF NOT EXISTS SP"),
        )
        self.assertEqual(
            "CREATE TABLE SP.t (id BIGINT)",
            goldilocks_compatible_statement(
                "CREATE TABLE IF NOT EXISTS SP.t (id BIGINT)"
            ),
        )
        self.assertEqual(
            "CREATE UNIQUE INDEX uq_t ON SP.t (id)",
            goldilocks_compatible_statement(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_t ON SP.t (id)"
            ),
        )
        self.assertIn(
            "FROM DUAL\nWHERE NOT EXISTS",
            goldilocks_compatible_statement(
                "INSERT INTO SP.data_provider (provider_code)\n"
                "SELECT 'krx'\n"
                "WHERE NOT EXISTS (SELECT 1 FROM SP.data_provider)"
            ),
        )

    def test_sql_literal_escapes_values(self):
        self.assertEqual("NULL", sql_literal(None))
        self.assertEqual("TRUE", sql_literal(True))
        self.assertEqual("42", sql_literal(42))
        self.assertEqual("'can''t'", sql_literal("can't"))

    def test_idempotent_create_detection_allows_leading_comments(self):
        self.assertTrue(
            is_idempotent_create_statement(
                "-- migration\nCREATE SCHEMA IF NOT EXISTS SP"
            )
        )

    def test_build_plan_counts_statements_and_checksums(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "001_test.sql"
            path.write_text("CREATE TABLE t (id BIGINT);\nINSERT INTO t VALUES (1);")

            plan = build_migration_plan([path])

        self.assertEqual("001_test.sql", plan[0].name)
        self.assertEqual(2, plan[0].statement_count)
        self.assertEqual(64, len(plan[0].checksum))

    def test_apply_migrations_records_then_skips_completed_files(self):
        with TemporaryDirectory() as directory:
            first = Path(directory) / "001_test.sql"
            first.write_text(
                "CREATE TABLE IF NOT EXISTS SP.schema_migration_note "
                "(migration_name VARCHAR(128), checksum VARCHAR(128));"
            )
            second = Path(directory) / "002_test.sql"
            second.write_text("CREATE TABLE sample_note (body VARCHAR(64));")
            connection = FakeConnection()

            first_results = apply_migrations(connection, [first, second])
            statement_count = len(connection.statements)
            second_results = apply_migrations(connection, [first, second])

        self.assertEqual(["applied", "applied"], [item.status for item in first_results])
        self.assertEqual(["skipped", "skipped"], [item.status for item in second_results])
        self.assertEqual(2, connection.commits)
        self.assertEqual(statement_count, len(connection.statements))

    def test_load_applied_migrations_does_not_mask_other_db_errors(self):
        with self.assertRaises(RuntimeError):
            load_applied_migrations(BrokenConnection())


if __name__ == "__main__":
    unittest.main()

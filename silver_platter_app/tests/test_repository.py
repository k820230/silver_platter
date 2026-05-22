from datetime import datetime
from datetime import date
from unittest import TestCase

from silver_platter.alerts import AlertDeliveryResult
from silver_platter.audit import AuditLog
from silver_platter.backtest import (
    BacktestOrderEvent,
    BacktestResult,
    BacktestRunConfig,
    ScenarioShock,
    StrategyOrderCandidate,
    apply_scenario_shock,
)
from silver_platter.backup import RestoreCheckResult
from silver_platter.data_pipeline import collect_price_bars
from silver_platter.headlines import Headline, deduplicate_headlines
from silver_platter.order_state import initial_order_state, transition_order_state
from silver_platter.providers import (
    ProviderMetadata,
    SecurityReference,
    StaticMarketDataProvider,
    license_policy_from_provider,
    sample_bar,
)
from silver_platter.repository import GoldilocksRepository
from silver_platter.risk_controls import headline_clusters_to_event_risk_signals
from silver_platter.verification import (
    DEFAULT_GATE_REQUIREMENTS,
    GateEvidence,
    assess_gate,
)


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, sql, params=None):
        self.connection.commands.append((sql, params))
        return self


class FakeConnection:
    def __init__(self):
        self.commands = []
        self.commits = 0

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1


class RepositoryTests(TestCase):
    def test_upsert_provider_uses_idempotent_insert(self):
        connection = FakeConnection()
        repository = GoldilocksRepository(connection)

        repository.upsert_provider(
            ProviderMetadata("sec_edgar", "disclosure", True, False, False),
            provider_name="SEC EDGAR",
            base_url="https://data.sec.gov",
            auth_type="user_agent",
        )

        sql, params = connection.commands[0]
        self.assertIn("INSERT INTO SP.data_provider", sql)
        self.assertIn("WHERE NOT EXISTS", sql)
        self.assertEqual("sec_edgar", params[0])
        self.assertEqual("sec_edgar", params[-1])

    def test_upsert_security_reference_uses_market_symbol_key(self):
        connection = FakeConnection()
        repository = GoldilocksRepository(connection)

        repository.upsert_security_reference(
            SecurityReference(
                symbol="AAPL",
                security_name="Apple Inc.",
                market_code="US",
                country_code="USA",
                currency="USD",
                asset_type="stock",
                exchange_code="NASDAQ",
                provider_symbol="AAPL",
            )
        )

        sql, params = connection.commands[0]
        self.assertIn("INSERT INTO SP.security_master", sql)
        self.assertIn("market_code = ? AND symbol = ?", sql)
        self.assertEqual(("US", "AAPL"), params[-2:])

    def test_insert_provider_symbol_map_persists_provider_mapping(self):
        connection = FakeConnection()
        repository = GoldilocksRepository(connection)
        valid_from = datetime(2026, 5, 22, 9, 0, 0)

        repository.insert_provider_symbol_map(7, 11, "AAPL", valid_from=valid_from)

        sql, params = connection.commands[0]
        self.assertIn("INSERT INTO SP.provider_symbol_map", sql)
        self.assertEqual((7, 11, "AAPL", valid_from, None), params)

    def test_insert_data_license_persists_entitlements(self):
        connection = FakeConnection()
        repository = GoldilocksRepository(connection)
        policy = license_policy_from_provider(
            ProviderMetadata("ofac", "headline", True, False, False)
        )

        repository.insert_data_license(7, policy)

        sql, params = connection.commands[0]
        self.assertIn("INSERT INTO SP.data_license", sql)
        self.assertEqual((7, "ofac_mvp_policy", True, True, False, False), params[:6])

    def test_write_price_bar_ingestion_persists_manifest_quality_and_bars(self):
        bar = sample_bar("AAPL", datetime(2026, 5, 22, 9, 0, 0), 200.0)
        ingestion = collect_price_bars(
            StaticMarketDataProvider("sec_edgar", [bar]),
            "AAPL",
        )
        connection = FakeConnection()
        repository = GoldilocksRepository(connection)

        repository.write_price_bar_ingestion(7, 11, ingestion)
        repository.commit()

        sql_commands = [command[0] for command in connection.commands]
        self.assertTrue(any("SP.raw_data_manifest" in sql for sql in sql_commands))
        self.assertTrue(any("SP.data_quality_run" in sql for sql in sql_commands))
        self.assertTrue(any("SP.price_bar" in sql for sql in sql_commands))
        self.assertEqual(1, connection.commits)
        self.assertEqual(11, connection.commands[-1][1][0])
        self.assertEqual(7, connection.commands[-1][1][1])

    def test_insert_audit_event_persists_json_detail(self):
        log = AuditLog()
        event = log.append(
            actor_type="system",
            actor_id="worker",
            action_code="ALERT_DELIVER",
            target_type="alert",
            target_id="a1",
            detail={"status": "delivered"},
            occurred_at=datetime(2026, 5, 22, 9, 0, 0),
        )
        connection = FakeConnection()
        repository = GoldilocksRepository(connection)

        repository.insert_audit_event(event)

        sql, params = connection.commands[0]
        self.assertIn("INSERT INTO SP.audit_log", sql)
        self.assertEqual("ALERT_DELIVER", params[2])
        self.assertEqual('{"status": "delivered"}', params[-1])

    def test_insert_order_state_event_and_idempotency_key(self):
        state = initial_order_state(
            "order-1",
            idempotency_key="key-1",
            now=datetime(2026, 5, 22, 9, 0, 0),
        )
        _, event = transition_order_state(
            state,
            "previewed",
            now=datetime(2026, 5, 22, 9, 1, 0),
        )
        connection = FakeConnection()
        repository = GoldilocksRepository(connection)

        repository.insert_order_state_event(33, event)
        repository.insert_order_idempotency_key(
            "key-1",
            33,
            reserved_at=datetime(2026, 5, 22, 9, 0, 0),
        )

        self.assertIn("SP.order_state_event", connection.commands[0][0])
        self.assertEqual((33, "draft", "previewed"), connection.commands[0][1][:3])
        self.assertIn("SP.order_idempotency_key", connection.commands[1][0])
        self.assertEqual(("key-1", 33), connection.commands[1][1][:2])

    def test_insert_backtest_run_and_result_tables(self):
        candidate = StrategyOrderCandidate(
            security_id="AAPL",
            side="buy",
            market="US",
            order_type="limit",
            price=200.0,
            quantity=3,
            decision_at=datetime(2026, 5, 22, 9, 0, 0),
            avg_daily_turnover_20d_krw=1_000_000_000,
        )
        result = BacktestResult(
            run_id="bt-1",
            status="completed",
            order_events=[BacktestOrderEvent(candidate, True, "filled", 12.5)],
            ending_cash_krw=99_000_000,
            realized_pnl_krw=12.5,
            blocked_order_count=0,
            lookahead_violation_count=0,
            metrics={"order_count": 1.0, "realized_return_pct": 0.00000125},
        )
        connection = FakeConnection()
        repository = GoldilocksRepository(connection)

        repository.insert_backtest_run(
            BacktestRunConfig("bt-1", "s1", date(2026, 5, 22), date(2026, 5, 23)),
            result,
            started_at=datetime(2026, 5, 22, 9, 0, 0),
            completed_at=datetime(2026, 5, 22, 9, 5, 0),
        )
        repository.write_backtest_result(44, result, {"AAPL": 11})

        sql_commands = [command[0] for command in connection.commands]
        self.assertTrue(any("SP.backtest_run" in sql for sql in sql_commands))
        self.assertTrue(any("SP.backtest_order_event" in sql for sql in sql_commands))
        self.assertTrue(any("SP.backtest_metric" in sql for sql in sql_commands))
        self.assertEqual(11, connection.commands[1][1][1])

    def test_insert_scenario_result(self):
        shock = ScenarioShock(
            scenario_id="s1",
            name="market drop",
            price_shock_pct=-0.1,
            fx_shock_pct=0.08,
            liquidity_multiplier=0.5,
        )
        result = apply_scenario_shock(100, 1300, 1_000_000_000, shock)
        connection = FakeConnection()
        repository = GoldilocksRepository(connection)
        created_at = datetime(2026, 5, 22, 9, 0, 0)

        repository.insert_scenario_result(shock, result, created_at=created_at)

        sql, params = connection.commands[0]
        self.assertIn("SP.scenario_result", sql)
        self.assertEqual(("s1", "market drop", 90.0, 1404.0), params[:4])
        self.assertEqual(created_at, params[5])
        self.assertIn('"liquidity_multiplier": 0.5', params[6])

    def test_insert_restore_check_run(self):
        connection = FakeConnection()
        repository = GoldilocksRepository(connection)
        checked_at = datetime(2026, 5, 22, 9, 0, 0)

        repository.insert_restore_check_run(
            RestoreCheckResult(
                status="failed",
                checked_at=checked_at,
                manifest_path="/backup/manifest.json",
                issue_count=1,
                issues=["checksum mismatch: part.dat"],
            ),
            backup_run_id=77,
        )

        sql, params = connection.commands[0]
        self.assertIn("SP.restore_check_run", sql)
        self.assertEqual((77, "/backup/manifest.json", checked_at, "failed", 1), params[:5])
        self.assertEqual('["checksum mismatch: part.dat"]', params[5])

    def test_insert_verification_gate_assessment_and_evidence(self):
        evidence = [
            GateEvidence("api_health", "pass", "GET /health", datetime(2026, 5, 22)),
            GateEvidence("web_health", "pass", "GET /", datetime(2026, 5, 22)),
            GateEvidence(
                "compose_config",
                "pass",
                "docker compose config",
                datetime(2026, 5, 22),
            ),
        ]
        assessment = assess_gate("G2", DEFAULT_GATE_REQUIREMENTS, evidence)
        connection = FakeConnection()
        repository = GoldilocksRepository(connection)

        repository.insert_gate_assessment(
            assessment,
            assessed_at=datetime(2026, 5, 22, 9, 0, 0),
        )
        repository.insert_gate_evidence("G2", evidence[0], gate_assessment_id=55)

        self.assertIn("SP.verification_gate_assessment", connection.commands[0][0])
        self.assertEqual(("G2", "pass", 3, 3), connection.commands[0][1][:4])
        self.assertIn("SP.verification_gate_evidence", connection.commands[1][0])
        self.assertEqual((55, "G2", "api_health", "pass"), connection.commands[1][1][:4])

    def test_insert_alert_delivery_result(self):
        connection = FakeConnection()
        repository = GoldilocksRepository(connection)

        repository.insert_alert_delivery_result(
            AlertDeliveryResult(
                provider_code="webhook",
                alert_id="ops-api",
                status="delivered",
                delivered_at=datetime(2026, 5, 22, 9, 0, 0),
            )
        )

        sql, params = connection.commands[0]
        self.assertIn("SP.alert_delivery_run", sql)
        self.assertEqual(("webhook", "ops-api", "delivered"), params[:3])

    def test_insert_headline_event_cluster_and_risk_signal(self):
        headline = Headline(
            provider="ofac",
            title="Counter Terrorism Designations",
            published_at=datetime(2026, 5, 21, 0, 0, 0),
            url="https://ofac.treasury.gov/recent-actions/20260521",
            security_ids=("AAPL",),
            group_ids=("semiconductor",),
            event_tags=("geopolitical", "sanction"),
            metadata={"raw_ref": "ofac-20260521"},
        )
        cluster = deduplicate_headlines([headline])[0]
        signal = headline_clusters_to_event_risk_signals([cluster])[0]
        connection = FakeConnection()
        repository = GoldilocksRepository(connection)

        repository.insert_headline_event(headline)
        repository.insert_headline_dedup_cluster(cluster)
        repository.insert_headline_risk_signal(signal)

        self.assertIn("SP.headline_event", connection.commands[0][0])
        self.assertEqual(("ofac", "ofac-20260521"), connection.commands[0][1][:2])
        self.assertIn("SP.headline_dedup_cluster", connection.commands[1][0])
        self.assertEqual(cluster.cluster_id, connection.commands[1][1][0])
        self.assertIn("SP.headline_risk_signal", connection.commands[2][0])
        self.assertEqual((cluster.cluster_id, "headline", "critical"), connection.commands[2][1][:3])

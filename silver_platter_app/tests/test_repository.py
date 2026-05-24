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
from silver_platter.charting import IndexObservation, build_index_chart_series
from silver_platter.data_pipeline import collect_price_bars
from silver_platter.headlines import Headline, deduplicate_headlines
from silver_platter.ml_ops import ModelErrorSummary, WatchlistRegistry
from silver_platter.order_state import initial_order_state, transition_order_state
from silver_platter.providers import (
    ProviderMetadata,
    SecurityReference,
    StaticMarketDataProvider,
    license_policy_from_provider,
    sample_bar,
)
from silver_platter.repository import GoldilocksRepository
from silver_platter.repository import _inline_params
from silver_platter.risk import OrderRiskInput, evaluate_order_risk
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

    def fetchone(self):
        if not self.connection.fetchone_results:
            return None
        return self.connection.fetchone_results.pop(0)

    def fetchall(self):
        if not self.connection.fetchall_results:
            return []
        return self.connection.fetchall_results.pop(0)


class FakeConnection:
    def __init__(self):
        self.commands = []
        self.commits = 0
        self.fetchone_results = []
        self.fetchall_results = []

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1


class BindingUnsupportedCursor:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, sql, params=None):
        if params is not None:
            raise RuntimeError("Optional feature not implemented: SQLBindParameter")
        self.connection.commands.append((sql, params))
        return self


class BindingUnsupportedConnection:
    def __init__(self):
        self.commands = []

    def cursor(self):
        return BindingUnsupportedCursor(self)


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
        self.assertIn("FROM DUAL", sql)
        self.assertIn("WHERE NOT EXISTS", sql)
        self.assertEqual("sec_edgar", params[0])
        self.assertEqual("sec_edgar", params[-1])

    def test_ensure_provider_id_upserts_and_reads_id(self):
        connection = FakeConnection()
        connection.fetchone_results = [(7,)]
        repository = GoldilocksRepository(connection)

        provider_id = repository.ensure_provider_id(
            ProviderMetadata("krx_data", "market_data", True, False, False)
        )

        self.assertEqual(7, provider_id)
        self.assertIn("INSERT INTO SP.data_provider", connection.commands[0][0])
        self.assertIn("SELECT provider_id", connection.commands[1][0])

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
        self.assertIn("FROM DUAL", sql)
        self.assertIn("market_code = ? AND symbol = ?", sql)
        self.assertEqual(("US", "AAPL"), params[-2:])

    def test_ensure_security_id_upserts_and_reads_id(self):
        connection = FakeConnection()
        connection.fetchone_results = [(11,)]
        repository = GoldilocksRepository(connection)

        security_id = repository.ensure_security_id(
            SecurityReference(
                symbol="005930",
                security_name="005930",
                market_code="KR",
                country_code="KOR",
                currency="KRW",
                asset_type="stock",
                exchange_code="KRX",
                provider_symbol="005930",
            )
        )

        self.assertEqual(11, security_id)
        self.assertIn("INSERT INTO SP.security_master", connection.commands[0][0])
        self.assertIn("SELECT security_id", connection.commands[1][0])

    def test_execute_inlines_params_when_driver_rejects_binding(self):
        connection = BindingUnsupportedConnection()
        repository = GoldilocksRepository(connection)

        repository.upsert_provider(
            ProviderMetadata("provider'1", "headline", True, False, False),
            provider_name="Provider One",
            base_url=None,
            auth_type="none",
        )

        sql, params = connection.commands[0]
        self.assertIsNone(params)
        self.assertIn("'provider''1'", sql)
        self.assertIn("NULL", sql)

    def test_inline_params_validates_placeholder_count(self):
        with self.assertRaises(ValueError):
            _inline_params("SELECT ? FROM DUAL WHERE x = ?", ("one",))

    def test_inline_params_renders_bool_literals(self):
        self.assertEqual(
            "INSERT INTO t VALUES (TRUE, FALSE)",
            _inline_params("INSERT INTO t VALUES (?, ?)", (True, False)),
        )

    def test_inline_params_renders_date_and_datetime_literals(self):
        self.assertEqual(
            "INSERT INTO t VALUES ('2026-05-24', '2026-05-24 09:30:00')",
            _inline_params(
                "INSERT INTO t VALUES (?, ?)",
                (date(2026, 5, 24), datetime(2026, 5, 24, 9, 30, 0)),
            ),
        )

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
        self.assertIn("WHERE NOT EXISTS", connection.commands[-1][0])

    def test_count_price_bars_reads_existing_rows(self):
        connection = FakeConnection()
        connection.fetchone_results = [(3,)]
        repository = GoldilocksRepository(connection)

        count = repository.count_price_bars(11, 7)

        self.assertEqual(3, count)
        self.assertIn("SELECT COUNT(*)", connection.commands[0][0])
        self.assertEqual((11, 7, "1d"), connection.commands[0][1])

    def test_list_price_history_securities_reads_grouped_price_bars(self):
        connection = FakeConnection()
        connection.fetchall_results = [
            [
                (
                    11,
                    "005930",
                    "Samsung Electronics",
                    "KR",
                    "KRX",
                    7,
                    "kis_domestic_daily_price",
                    "KIS",
                    "1d",
                    300,
                    datetime(2025, 7, 30, 16, 0, 0),
                    datetime(2026, 5, 22, 16, 0, 0),
                )
            ]
        ]
        connection.fetchone_results = [(203000, 1200000)]
        repository = GoldilocksRepository(connection)

        items = repository.list_price_history_securities(limit=20)

        self.assertEqual("005930", items[0]["security_id"])
        self.assertEqual(300, items[0]["bar_count"])
        self.assertEqual(203000.0, items[0]["latest_close_price"])
        self.assertEqual(1200000.0, items[0]["latest_volume"])
        self.assertEqual("kis_domestic_daily_price", items[0]["provider_code"])
        self.assertIn("GROUP BY", connection.commands[0][0])

    def test_search_securities_matches_partial_name_and_symbol(self):
        connection = FakeConnection()
        connection.fetchall_results = [
            [
                (11, "005930", "Samsung Electronics", "KR", "KRX", "KRW"),
                (12, "000660", "SK Hynix", "KR", "KRX", "KRW"),
            ]
        ]
        connection.fetchone_results = [
            (71000, 1200000, datetime(2026, 5, 22, 16, 0, 0)),
            (1941000, 500000, datetime(2026, 5, 22, 16, 0, 0)),
        ]
        repository = GoldilocksRepository(connection)

        items = repository.search_securities("sam", market_code="KR", limit=20)

        self.assertEqual("005930", items[0]["security_id"])
        self.assertEqual("Samsung Electronics", items[0]["security_name"])
        self.assertEqual(71000.0, items[0]["latest_close_price"])
        self.assertIn("LOWER(security_name) LIKE", connection.commands[0][0])
        self.assertEqual(("KR", "KR", "%sam%", "%sam%"), connection.commands[0][1])

    def test_get_price_history_bars_reads_latest_rows_in_time_order(self):
        connection = FakeConnection()
        connection.fetchall_results = [
            [
                (
                    "005930",
                    datetime(2026, 5, 22, 16, 0, 0),
                    71000,
                    2000,
                    142000000,
                    datetime(2026, 5, 22, 16, 0, 0),
                ),
                (
                    "005930",
                    datetime(2026, 5, 21, 16, 0, 0),
                    70000,
                    1000,
                    70000000,
                    datetime(2026, 5, 21, 16, 0, 0),
                ),
            ]
        ]
        repository = GoldilocksRepository(connection)

        bars = repository.get_price_history_bars("KR", "005930", limit=2)

        self.assertEqual(
            [
                datetime(2026, 5, 21, 16, 0, 0),
                datetime(2026, 5, 22, 16, 0, 0),
            ],
            [bar.bar_ts for bar in bars],
        )
        self.assertEqual(70000.0, bars[0].close_price)
        self.assertEqual(("KR", "005930", "1d"), connection.commands[0][1])

    def test_insert_user_watchlist_item_and_deactivate(self):
        registry = WatchlistRegistry()
        item = registry.add("u1", "AAPL", note="core")
        connection = FakeConnection()
        repository = GoldilocksRepository(connection)
        deactivated_at = datetime(2026, 5, 23, 9, 0, 0)

        repository.insert_user_watchlist_item(item, security_id=11)
        repository.deactivate_user_watchlist_item(
            "u1",
            security_id=11,
            deactivated_at=deactivated_at,
        )

        self.assertIn("SP.user_watchlist", connection.commands[0][0])
        self.assertEqual(("u1", 11, "core"), connection.commands[0][1][:3])
        self.assertTrue(connection.commands[0][1][-1])
        self.assertIn("UPDATE SP.user_watchlist", connection.commands[1][0])
        self.assertEqual((deactivated_at, "u1", 11), connection.commands[1][1])

    def test_insert_model_error_summary(self):
        connection = FakeConnection()
        repository = GoldilocksRepository(connection)
        calculated_at = datetime(2026, 5, 24, 9, 0, 0)

        repository.insert_model_error_summary(
            security_id=11,
            model_version="baseline-0.1",
            horizon="1d",
            summary=ModelErrorSummary(
                security_id="AAPL",
                sample_count=3,
                mean_absolute_error=1.25,
                mean_absolute_pct_error=0.01,
            ),
            calculated_at=calculated_at,
        )

        sql, params = connection.commands[0]
        self.assertIn("SP.ml_model_performance_summary", sql)
        self.assertEqual((11, "baseline-0.1", "1d", 3, 1.25, 0.01, calculated_at), params)

    def test_insert_index_chart_snapshot(self):
        connection = FakeConnection()
        repository = GoldilocksRepository(connection)
        generated_at = datetime(2026, 5, 24, 9, 0, 0)
        series = build_index_chart_series(
            [
                IndexObservation("AAPL", datetime(2026, 5, 22, 9, 0, 0), 32.5, 30.1),
                IndexObservation("AAPL", datetime(2026, 5, 23, 9, 0, 0), 34.0, 31.2),
            ],
            "AAPL",
        )

        repository.insert_index_chart_snapshot(
            security_id=11,
            series=series,
            generated_at=generated_at,
        )

        sql, params = connection.commands[0]
        self.assertIn("SP.index_chart_snapshot", sql)
        self.assertEqual((11, "volatility_risk", None, None, generated_at, 2), params[:6])
        self.assertIn('"security_id": "AAPL"', params[6])

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

    def test_insert_risk_check_result(self):
        decision = evaluate_order_risk(
            OrderRiskInput(
                order_amount_krw=2_000_000_000,
                avg_daily_turnover_20d_krw=10_000_000_000,
                market="KR",
                order_type="limit",
            )
        )
        connection = FakeConnection()
        repository = GoldilocksRepository(connection)

        repository.insert_risk_check_result(
            33,
            decision,
            checked_at=datetime(2026, 5, 22, 9, 0, 0),
        )

        self.assertIn("SP.risk_check_result", connection.commands[0][0])
        self.assertEqual((33, "block"), connection.commands[0][1][:2])
        self.assertIn("AMOUNT_ABOVE_MAX", connection.commands[0][1][4])

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

    def test_insert_db_backup_run(self):
        connection = FakeConnection()
        repository = GoldilocksRepository(connection)

        repository.insert_db_backup_run(
            backup_policy_id=7,
            scheduled_at=datetime(2026, 5, 23, 10, 0, 0),
            started_at=datetime(2026, 5, 23, 10, 0, 1),
            completed_at=datetime(2026, 5, 23, 10, 1, 0),
            status="success",
            backup_path="/backup/2026-05-23",
            total_bytes=1024,
            checksum_status="ok",
        )

        self.assertIn("SP.db_backup_run", connection.commands[0][0])
        self.assertEqual((7, datetime(2026, 5, 23, 10, 0, 0)), connection.commands[0][1][:2])

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

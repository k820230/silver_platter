from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from fastapi import HTTPException

import silver_platter.api.main as api_main
from silver_platter.api.main import (
    ActualPriceBarRequest,
    BacktestRunRequest,
    ExportedSnapshotReplayRequest,
    FeatureSnapshotRequest,
    MlPredictionJobRequest,
    PriceBarQualityItem,
    backtest_replay_exported_snapshot,
    backtest_run,
    backtest_strategy_plugins,
    current_price_history_risk,
    headline_risk_signals,
    HeadlineRiskSignalsRequest,
    audit_setting_change_append,
    ml_job_run,
    market_volume_leaders,
    operations_backup_status,
    operations_provider_health,
    price_history_risk_chart,
    price_history_securities,
    provider_catalog,
    security_search,
    SecuritySearchRequest,
    SettingChangeAuditRequest,
    watchlist_add,
    watchlist_list,
    watchlist_remove,
    WatchlistAddRequest,
)
from silver_platter.backup import build_backup_manifest, write_backup_manifest
from silver_platter.exports import export_price_bars_partitioned
from silver_platter.audit import AuditLog
from silver_platter.data_quality import PriceBarInput
from silver_platter.ml_ops import WatchlistRegistry
from silver_platter.providers import sample_bar


class ApiBoundaryTests(TestCase):
    def test_price_history_securities_lists_db_backed_symbols(self):
        class FakeConnection:
            def __init__(self):
                self.closed = False

            def close(self):
                self.closed = True

        class FakeRepository:
            def __init__(self, connection):
                self.connection = connection

            def list_price_history_securities(self, limit):
                return [
                    {
                        "security_id": "005930",
                        "market": "KR",
                        "bar_count": 300,
                        "latest_close_price": 203000.0,
                    }
                ][:limit]

        connection = FakeConnection()
        with patch.object(api_main, "connect_goldilocks_from_env", return_value=connection), patch.object(
            api_main,
            "GoldilocksRepository",
            FakeRepository,
        ):
            payload = price_history_securities(limit=20)

        self.assertEqual("005930", payload["items"][0]["security_id"])
        self.assertEqual(203000.0, payload["items"][0]["latest_close_price"])
        self.assertTrue(connection.closed)

    def test_price_history_risk_chart_returns_db_backed_chart(self):
        class FakeConnection:
            def close(self):
                pass

        class FakeRepository:
            def __init__(self, connection):
                self.connection = connection

            def get_price_history_bars(self, market, security_id, bar_interval, limit):
                base = datetime(2026, 5, 1, 16, 0, 0)
                return [
                    PriceBarInput(
                        security_id=security_id,
                        bar_ts=base.replace(day=index + 1),
                        close_price=70000 + index * 300,
                        volume=1000000 + index,
                        turnover_krw=70000000000,
                        available_to_model_at=base.replace(day=index + 1),
                    )
                    for index in range(22)
                ]

        with patch.object(api_main, "connect_goldilocks_from_env", return_value=FakeConnection()), patch.object(
            api_main,
            "GoldilocksRepository",
            FakeRepository,
        ):
            payload = price_history_risk_chart("005930", market="KR", risk_range="1d", limit=20)

        self.assertEqual("005930", payload["security_id"])
        self.assertEqual("1d", payload["risk_range"])
        self.assertEqual(20, len(payload["points"]))

    def test_current_price_history_risk_returns_db_backed_assessment(self):
        class FakeConnection:
            def close(self):
                pass

        class FakeRepository:
            def __init__(self, connection):
                self.connection = connection

            def get_price_history_bars(self, market, security_id, bar_interval, limit):
                base = datetime(2026, 5, 1, 16, 0, 0)
                return [
                    PriceBarInput(
                        security_id=security_id,
                        bar_ts=base.replace(day=index + 1),
                        close_price=70000 + index * 300,
                        volume=1000000 + index,
                        turnover_krw=70000000000,
                        available_to_model_at=base.replace(day=index + 1),
                    )
                    for index in range(22)
                ]

        with patch.object(api_main, "connect_goldilocks_from_env", return_value=FakeConnection()), patch.object(
            api_main,
            "GoldilocksRepository",
            FakeRepository,
        ):
            payload = current_price_history_risk(
                "005930",
                current_price=76500,
                market="KR",
                risk_range="1w",
                limit=20,
            )

        self.assertEqual("005930", payload["security_id"])
        self.assertEqual(76500, payload["current_price"])
        self.assertGreater(payload["risk_score"], 0)
        self.assertIn("입력 현재가", payload["summary"])

    def test_strategy_plugins_endpoint_lists_builtin_plugins(self):
        response = backtest_strategy_plugins()

        self.assertEqual(
            ["fixed-close", "momentum-threshold"],
            [item["plugin_id"] for item in response["plugins"]],
        )

    def test_backtest_run_unknown_strategy_plugin_returns_400(self):
        with self.assertRaises(HTTPException) as raised:
            backtest_run(
                BacktestRunRequest(
                    run_id="api-bt",
                    strategy_id="api",
                    strategy_plugin_id="missing-plugin",
                    from_date=date(2026, 5, 22),
                    to_date=date(2026, 5, 22),
                    security_id="AAPL",
                    market="US",
                    quantity=1,
                    avg_daily_turnover_20d_krw=1_000_000_000,
                    bars=[
                        PriceBarQualityItem(
                            security_id="AAPL",
                            bar_ts=datetime(2026, 5, 22, 9, 0, 0),
                            close_price=200.0,
                            volume=1000,
                            turnover_krw=200000,
                            available_to_model_at=datetime(2026, 5, 22, 9, 0, 0),
                        )
                    ],
                )
            )

        self.assertEqual(400, raised.exception.status_code)
        self.assertIn("unknown strategy plugin", raised.exception.detail)

    def test_replay_exported_snapshot_missing_path_returns_400(self):
        with self.assertRaises(HTTPException) as raised:
            backtest_replay_exported_snapshot(
                ExportedSnapshotReplayRequest(
                    run_id="api-replay",
                    strategy_id="api",
                    from_date=date(2026, 5, 22),
                    to_date=date(2026, 5, 22),
                    security_id="AAPL",
                    snapshot_paths=["/tmp/silver-platter-missing-snapshot.jsonl"],
                )
            )

        self.assertEqual(400, raised.exception.status_code)
        self.assertIn("silver-platter-missing-snapshot", raised.exception.detail)

    def test_replay_exported_snapshot_accepts_strategy_parameters(self):
        with TemporaryDirectory() as tmp:
            export_price_bars_partitioned(
                [
                    sample_bar("AAPL", datetime(2026, 5, 22, 9, 0, 0), 100.0),
                    sample_bar("AAPL", datetime(2026, 5, 23, 9, 0, 0), 102.0),
                ],
                Path(tmp),
                provider_code="free",
                prefer_parquet=False,
            )

            payload = backtest_replay_exported_snapshot(
                ExportedSnapshotReplayRequest(
                    run_id="api-replay",
                    strategy_id="api",
                    strategy_plugin_id="momentum-threshold",
                    strategy_parameters={"min_return_pct": 0.01},
                    from_date=date(2026, 5, 22),
                    to_date=date(2026, 5, 23),
                    security_id="AAPL",
                    market="US",
                    snapshot_paths=[tmp],
                )
            )

        self.assertEqual("momentum-threshold", payload["strategy_plugin_id"])
        self.assertEqual(1, len(payload["order_events"]))

    def test_provider_health_endpoint_reports_unconfigured_providers(self):
        with patch.dict(
            "os.environ",
            {
                "OPENDART_API_KEY": "",
                "ECOS_API_KEY": "",
                "SEC_EDGAR_USER_AGENT": "Silver Platter admin@example.com",
                "KRX_KIND_SMOKE_ENABLED": "0",
                "KRX_PRICE_SMOKE_ENABLED": "0",
            },
        ):
            payload = operations_provider_health()

        statuses = {
            component["component"]: component["status"]
            for component in payload["components"]
        }
        details = {
            component["component"]: component["detail"]
            for component in payload["components"]
        }
        self.assertEqual("degraded", payload["status"])
        self.assertEqual("degraded", statuses["provider:opendart:disclosure"])
        self.assertEqual("degraded", statuses["provider:ecos_bok:fx"])
        self.assertEqual("ready", statuses["provider:krx_free:reference_data"])
        self.assertIn("license=opendart_mvp_policy", details["provider:opendart:disclosure"])
        self.assertIn("redistribute=False", details["provider:opendart:disclosure"])

    def test_provider_catalog_endpoint_lists_structured_license_policies(self):
        payload = provider_catalog()

        providers = {
            (item["provider_code"], item["provider_type"]): item
            for item in payload["providers"]
        }
        self.assertIn(("krx_free", "reference_data"), providers)
        self.assertIn(("ofac", "headline"), providers)
        ofac_policy = providers[("ofac", "headline")]["license_policy"]
        self.assertEqual("ofac_mvp_policy", ofac_policy["license_name"])
        self.assertTrue(ofac_policy["can_store"])
        self.assertTrue(ofac_policy["can_transform"])
        self.assertFalse(ofac_policy["can_display_realtime"])
        self.assertFalse(ofac_policy["can_redistribute"])

    def test_setting_change_audit_endpoint_records_diff_and_actor_context(self):
        api_main.AUDIT_LOG = AuditLog()

        payload = audit_setting_change_append(
            SettingChangeAuditRequest(
                user_id="u1",
                session_id="s1",
                source="web",
                target_id="risk.max_order",
                before={"max_order_krw": 1_000_000},
                after={"max_order_krw": 2_000_000},
            )
        )

        self.assertEqual("SETTING_CHANGE", payload["action_code"])
        self.assertEqual("u1", payload["actor_id"])
        self.assertEqual("u1", payload["detail"]["actor_user_id"])
        self.assertIn("max_order_krw", payload["detail"]["changed_keys"])
        self.assertIn("1000000", payload["detail"]["before"])

    def test_backup_status_endpoint_reports_invalid_manifest_as_critical(self):
        with TemporaryDirectory() as tmp:
            Path(tmp, "manifest.json").write_text("{not-json", encoding="utf-8")

            payload = operations_backup_status(backup_base_dir=tmp)

        self.assertEqual("critical", payload["status"])
        self.assertEqual("failed", payload["restore_status"])
        self.assertEqual("unknown", payload["backup_status"])
        self.assertIn("manifest is not valid json", payload["issues"])

    def test_backup_status_endpoint_accepts_max_backup_age_days(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            data_file = base / "goldilocks" / "data" / "part.dat"
            data_file.parent.mkdir(parents=True)
            data_file.write_text("payload", encoding="utf-8")
            write_backup_manifest(
                build_backup_manifest(base, date.today()),
                base / "manifest.json",
            )

            payload = operations_backup_status(
                backup_base_dir=tmp,
                max_backup_age_days=1,
            )

        self.assertEqual("ok", payload["status"])

    def test_backup_status_endpoint_includes_restore_drill_evidence(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            data_file = base / "goldilocks" / "data" / "part.dat"
            data_file.parent.mkdir(parents=True)
            data_file.write_text("payload", encoding="utf-8")
            write_backup_manifest(
                build_backup_manifest(base, date.today()),
                base / "manifest.json",
            )
            evidence_path = base / ".restore_drill_runs" / "2026-06-01.json"
            evidence_path.parent.mkdir(parents=True)
            evidence_path.write_text(
                (
                    '{"completed_at":"2026-06-01T11:02:00+09:00",'
                    '"scheduled_at":"2026-06-01T11:00:00+09:00",'
                    '"status":"ok"}'
                ),
                encoding="utf-8",
            )

            payload = operations_backup_status(backup_base_dir=tmp)

        self.assertEqual(str(evidence_path), payload["latest_restore_drill_path"])
        self.assertEqual("ok", payload["restore_drill_status"])
        self.assertEqual(
            "2026-06-01T11:02:00+09:00",
            payload["restore_drill_checked_at"],
        )

    def test_backup_status_endpoint_rejects_invalid_max_backup_age_days(self):
        with self.assertRaises(HTTPException) as raised:
            operations_backup_status(max_backup_age_days=0)

        self.assertEqual(400, raised.exception.status_code)
        self.assertIn("max_backup_age_days", raised.exception.detail)

    def test_watchlist_api_persists_when_store_path_configured(self):
        with TemporaryDirectory() as tmp, patch.dict(
            "os.environ",
            {"WATCHLIST_STORE_PATH": str(Path(tmp) / "watchlist.json")},
        ):
            api_main.WATCHLISTS = WatchlistRegistry()
            api_main.WATCHLIST_STORE_LOADED_FROM = None
            watchlist_add(WatchlistAddRequest(user_id="u1", security_id="AAPL", note="core"))

            api_main.WATCHLISTS = WatchlistRegistry()
            api_main.WATCHLIST_STORE_LOADED_FROM = None
            listed = watchlist_list("u1")
            removed = watchlist_remove("u1", "AAPL")
            api_main.WATCHLISTS = WatchlistRegistry()
            api_main.WATCHLIST_STORE_LOADED_FROM = None
            listed_after_remove = watchlist_list("u1")

        self.assertEqual(["AAPL"], [item["security_id"] for item in listed["items"]])
        self.assertEqual("core", listed["items"][0]["note"])
        self.assertTrue(removed["removed"])
        self.assertEqual([], listed_after_remove["items"])

    def test_watchlist_add_prefetches_history_for_new_security(self):
        api_main.WATCHLISTS = WatchlistRegistry()
        api_main.WATCHLIST_STORE_LOADED_FROM = None
        with patch.object(
            api_main,
            "_prefetch_history_for_security",
            return_value={"status": "stored", "bar_count": 10},
        ) as prefetch:
            payload = watchlist_add(
                WatchlistAddRequest(
                    user_id="u1",
                    security_id="005930.KS",
                    market="KR",
                )
            )

        self.assertEqual("stored", payload["history_prefetch"]["status"])
        prefetch.assert_called_once()
        self.assertEqual("005930.KS", prefetch.call_args.args[0])
        self.assertEqual("KR", prefetch.call_args.args[1])

    def test_watchlist_add_skips_prefetch_for_existing_active_security(self):
        api_main.WATCHLISTS = WatchlistRegistry()
        api_main.WATCHLIST_STORE_LOADED_FROM = None
        watchlist_add(
            WatchlistAddRequest(
                user_id="u1",
                security_id="AAPL",
                prefetch_history=False,
            )
        )

        payload = watchlist_add(WatchlistAddRequest(user_id="u1", security_id="AAPL"))

        self.assertEqual(
            "skipped_existing_watchlist",
            payload["history_prefetch"]["status"],
        )

    def test_security_search_can_prefetch_history(self):
        with patch.object(
            api_main,
            "_prefetch_history_for_security",
            return_value={"status": "stored", "bar_count": 10},
        ) as prefetch:
            payload = security_search(
                SecuritySearchRequest(
                    security_id="005930.KS",
                    market="KR",
                )
            )

        self.assertEqual("005930", payload["security"]["security_id"])
        self.assertEqual("stored", payload["history_prefetch"]["status"])
        prefetch.assert_called_once()

    def test_market_volume_leaders_returns_two_market_lists(self):
        api_main.VOLUME_LEADERS_CACHE.clear()
        payload = {
            "generated_at": "2026-05-24T00:00:00",
            "limit": 20,
            "markets": [
                {"market": "KR", "status": "ready", "source": "test", "detail": "", "items": []},
                {"market": "US", "status": "ready", "source": "test", "detail": "", "items": []},
            ],
        }
        with patch.object(api_main, "_load_volume_leaders", return_value=payload) as loader:
            result = market_volume_leaders()

        loader.assert_called_once_with(20)
        self.assertEqual(["KR", "US"], [item["market"] for item in result["markets"]])

    def test_market_volume_leaders_rejects_invalid_limit(self):
        with self.assertRaises(HTTPException) as raised:
            market_volume_leaders(limit=0)

        self.assertEqual(400, raised.exception.status_code)
        self.assertIn("limit", raised.exception.detail)

    def test_ml_job_run_matches_actual_bars_when_observed(self):
        payload = ml_job_run(
            MlPredictionJobRequest(
                job_id="api-ml-actual",
                snapshot=FeatureSnapshotRequest(
                    security_id="AAPL",
                    as_of=datetime(2026, 5, 22, 9, 0, 0),
                    last_price=200.0,
                    avg_volume_20d=50_000_000,
                    annualized_volatility=0.30,
                    risk_score=35.0,
                ),
                horizons=["1d"],
                actual_bars=[
                    ActualPriceBarRequest(
                        security_id="AAPL",
                        bar_ts=datetime(2026, 5, 23, 15, 0, 0),
                        close_price=203.0,
                        volume=1_000_000,
                        turnover_krw=10_000_000_000,
                        available_to_model_at=datetime(2026, 5, 23, 16, 0, 0),
                    )
                ],
                observed_at=datetime(2026, 5, 23, 17, 0, 0),
            )
        )

        self.assertEqual(203.0, payload["predictions"][0]["actual_price"])
        self.assertIsNotNone(payload["predictions"][0]["absolute_error"])
        self.assertEqual(1, payload["error_summary"]["sample_count"])
        self.assertGreater(payload["error_summary"]["mean_absolute_error"], 0)

    def test_headline_risk_signals_endpoint_deduplicates_and_maps_signal(self):
        payload = headline_risk_signals(
            HeadlineRiskSignalsRequest(
                headlines=[
                    {
                        "provider": "federal_reserve",
                        "title": "Sanction shock affects chip exports",
                        "published_at": datetime(2026, 5, 22, 9, 0, 0),
                        "url": "https://www.federalreserve.gov/a",
                        "security_ids": ["005930"],
                        "group_ids": ["semiconductor"],
                        "event_tags": ["geopolitical", "sanction"],
                    },
                    {
                        "provider": "ecb",
                        "title": "Sanction shock affects chip exports",
                        "published_at": datetime(2026, 5, 22, 9, 5, 0),
                        "url": "https://www.ecb.europa.eu/b",
                        "group_ids": ["semiconductor"],
                        "event_tags": ["geopolitical", "sanction"],
                    },
                ]
            )
        )

        self.assertEqual(1, len(payload["clusters"]))
        self.assertEqual(1, len(payload["signals"]))
        self.assertEqual("critical", payload["signals"][0]["severity"])
        self.assertEqual(["005930"], payload["signals"][0]["security_ids"])

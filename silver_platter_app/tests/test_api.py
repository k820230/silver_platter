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
    headline_risk_signals,
    HeadlineRiskSignalsRequest,
    ml_job_run,
    operations_backup_status,
    operations_provider_health,
    provider_catalog,
    watchlist_add,
    watchlist_list,
    watchlist_remove,
    WatchlistAddRequest,
)
from silver_platter.backup import build_backup_manifest, write_backup_manifest
from silver_platter.exports import export_price_bars_partitioned
from silver_platter.ml_ops import WatchlistRegistry
from silver_platter.providers import sample_bar


class ApiBoundaryTests(TestCase):
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

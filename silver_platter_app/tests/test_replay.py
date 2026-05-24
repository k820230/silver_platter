from contextlib import redirect_stdout
from datetime import date, datetime
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from silver_platter.exports import export_price_bars_partitioned
from silver_platter.providers import sample_bar
from silver_platter.replay import (
    ExportedSnapshotReplayConfig,
    main,
    run_exported_snapshot_replay,
)


class ExportedSnapshotReplayTests(TestCase):
    def test_run_exported_snapshot_replay_filters_security_and_builds_evidence(self):
        bars = [
            sample_bar("AAPL", datetime(2026, 5, 22, 9, 0, 0), 200.0),
            sample_bar("MSFT", datetime(2026, 5, 22, 9, 0, 0), 410.0),
            sample_bar("AAPL", datetime(2026, 5, 23, 9, 0, 0), 201.0),
        ]
        with TemporaryDirectory() as tmp:
            export_price_bars_partitioned(
                bars,
                Path(tmp),
                provider_code="free",
                prefer_parquet=False,
            )

            result = run_exported_snapshot_replay(
                ExportedSnapshotReplayConfig(
                    run_id="replay-1",
                    strategy_id="fixed-close",
                    from_date=date(2026, 5, 22),
                    to_date=date(2026, 5, 23),
                    security_id="AAPL",
                    snapshot_paths=[Path(tmp)],
                    market="US",
                    quantity=1,
                    required_min_days=2,
                    replay_seed="seed-1",
                )
            )

        self.assertEqual("completed", result.backtest.status)
        self.assertEqual(3, result.loaded_bar_count)
        self.assertEqual(2, result.replay_bar_count)
        self.assertEqual(2, len(result.backtest.order_events))
        self.assertEqual("pass", result.paper_replay_evidence.status)
        self.assertEqual(3.0, result.backtest.metrics["loaded_bar_count"])
        self.assertEqual(2.0, result.backtest.metrics["replay_bar_count"])
        self.assertEqual("seed-1", result.as_dict()["replay_seed"])

    def test_run_exported_snapshot_replay_fails_when_security_missing(self):
        bars = [sample_bar("MSFT", datetime(2026, 5, 22, 9, 0, 0), 410.0)]
        with TemporaryDirectory() as tmp:
            export_price_bars_partitioned(
                bars,
                Path(tmp),
                provider_code="free",
                prefer_parquet=False,
            )

            with self.assertRaisesRegex(ValueError, "no bars found for security_id"):
                run_exported_snapshot_replay(
                    ExportedSnapshotReplayConfig(
                        run_id="replay-2",
                        strategy_id="fixed-close",
                        from_date=date(2026, 5, 22),
                        to_date=date(2026, 5, 22),
                        security_id="AAPL",
                        snapshot_paths=[Path(tmp)],
                    )
                )

    def test_run_exported_snapshot_replay_uses_strategy_plugin(self):
        bars = [
            sample_bar("AAPL", datetime(2026, 5, 22, 9, 0, 0), 100.0),
            sample_bar("AAPL", datetime(2026, 5, 23, 9, 0, 0), 100.5),
            sample_bar("AAPL", datetime(2026, 5, 24, 9, 0, 0), 102.0),
        ]
        with TemporaryDirectory() as tmp:
            export_price_bars_partitioned(
                bars,
                Path(tmp),
                provider_code="free",
                prefer_parquet=False,
            )

            result = run_exported_snapshot_replay(
                ExportedSnapshotReplayConfig(
                    run_id="replay-plugin",
                    strategy_id="momentum-test",
                    from_date=date(2026, 5, 22),
                    to_date=date(2026, 5, 24),
                    security_id="AAPL",
                    snapshot_paths=[Path(tmp)],
                    market="US",
                    strategy_plugin_id="momentum-threshold",
                    strategy_parameters={"min_return_pct": 0.01},
                )
            )

        self.assertEqual(1, len(result.backtest.order_events))
        self.assertEqual("momentum-threshold", result.as_dict()["strategy_plugin_id"])

    def test_replay_cli_prints_json_result(self):
        bars = [sample_bar("AAPL", datetime(2026, 5, 22, 9, 0, 0), 200.0)]
        with TemporaryDirectory() as tmp:
            export_price_bars_partitioned(
                bars,
                Path(tmp),
                provider_code="free",
                prefer_parquet=False,
            )

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "--run-id",
                        "replay-cli",
                        "--strategy-id",
                        "fixed-close",
                        "--from-date",
                        "2026-05-22",
                        "--to-date",
                        "2026-05-22",
                        "--security-id",
                        "AAPL",
                        "--snapshot-path",
                        tmp,
                    ]
                )

        self.assertEqual(0, exit_code)
        payload = json.loads(output.getvalue())
        self.assertEqual("replay-cli", payload["run_id"])
        self.assertEqual("pass", payload["paper_replay_evidence"]["status"])

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from silver_platter.exports import (
    export_price_bars_partitioned,
    load_price_bars_from_exported_files,
    load_price_bars_from_paths,
)
from silver_platter.providers import sample_bar


class ExportTests(TestCase):
    def test_export_price_bars_partitioned_writes_file_and_manifest(self):
        bars = [
            sample_bar("AAPL", datetime(2026, 5, 22, 9, 0, 0), 200.0),
            sample_bar("AAPL", datetime(2026, 5, 22, 9, 1, 0), 201.0),
        ]
        with TemporaryDirectory() as tmp:
            result = export_price_bars_partitioned(
                bars,
                Path(tmp),
                provider_code="free",
                prefer_parquet=False,
            )

            self.assertEqual(2, result.row_count)
            self.assertEqual("jsonl", result.written_format)
            self.assertEqual(1, len(result.files))
            self.assertTrue(Path(result.files[0].path).exists())
            self.assertEqual(64, len(result.files[0].content_sha256))

    def test_load_price_bars_from_exported_jsonl_files_round_trips_snapshot(self):
        bars = [
            sample_bar("AAPL", datetime(2026, 5, 22, 9, 0, 0), 200.0),
            sample_bar("MSFT", datetime(2026, 5, 23, 9, 0, 0), 410.0),
        ]
        with TemporaryDirectory() as tmp:
            result = export_price_bars_partitioned(
                bars,
                Path(tmp),
                provider_code="free",
                prefer_parquet=False,
            )

            loaded = load_price_bars_from_exported_files(result.files)

        self.assertEqual(["AAPL", "MSFT"], [bar.security_id for bar in loaded])
        self.assertEqual([200.0, 410.0], [bar.close_price for bar in loaded])

    def test_load_price_bars_from_paths_discovers_partitioned_files(self):
        bars = [
            sample_bar("AAPL", datetime(2026, 5, 22, 9, 0, 0), 200.0),
            sample_bar("AAPL", datetime(2026, 5, 23, 9, 0, 0), 201.0),
        ]
        with TemporaryDirectory() as tmp:
            export_price_bars_partitioned(
                bars,
                Path(tmp),
                provider_code="free",
                prefer_parquet=False,
            )

            loaded = load_price_bars_from_paths([Path(tmp)])

        self.assertEqual(2, len(loaded))
        self.assertEqual([200.0, 201.0], [bar.close_price for bar in loaded])

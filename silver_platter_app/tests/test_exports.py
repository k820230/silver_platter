from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from silver_platter.exports import export_price_bars_partitioned
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

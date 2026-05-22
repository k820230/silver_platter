from datetime import datetime
from unittest import TestCase

from silver_platter.charting import IndexObservation, build_index_chart_series


class ChartingTests(TestCase):
    def test_build_index_chart_series_filters_and_sorts(self):
        series = build_index_chart_series(
            [
                IndexObservation("AAPL", datetime(2026, 5, 23), 42.0, 35.0),
                IndexObservation("MSFT", datetime(2026, 5, 22), 30.0, 20.0),
                IndexObservation("AAPL", datetime(2026, 5, 22), 40.0, 33.0),
            ],
            "AAPL",
        )

        self.assertEqual(2, len(series.points))
        self.assertEqual(datetime(2026, 5, 22), series.points[0].observed_at)
        self.assertEqual("AAPL", series.as_dict()["security_id"])

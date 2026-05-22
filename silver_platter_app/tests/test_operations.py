from datetime import datetime
from unittest import TestCase

from silver_platter.operations import ComponentStatus, summarize_operations


class OperationsTests(TestCase):
    def test_operations_summary_degraded_for_component_warning(self):
        summary = summarize_operations(
            [
                ComponentStatus("api", "ok", "ready", datetime(2026, 5, 22, 9, 0, 0)),
                ComponentStatus("backup", "failed", "checksum mismatch", datetime(2026, 5, 22, 9, 0, 0)),
            ],
            generated_at=datetime(2026, 5, 22, 9, 1, 0),
        )

        self.assertEqual("critical", summary.status)
        self.assertEqual(1, summary.open_issue_count)
        self.assertEqual("api", summary.as_dict()["components"][0]["component"])

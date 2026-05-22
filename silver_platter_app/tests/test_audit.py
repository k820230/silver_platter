from datetime import datetime
from unittest import TestCase

from silver_platter.audit import AuditLog, filter_audit_events


class AuditTests(TestCase):
    def test_append_and_filter_audit_events(self):
        log = AuditLog()
        first = log.append(
            actor_type="system",
            actor_id="worker",
            action_code="ORDER_SUBMIT",
            target_type="order",
            target_id="o1",
            occurred_at=datetime(2026, 5, 22, 9, 0, 0),
        )
        log.append(
            actor_type="system",
            actor_id="worker",
            action_code="BACKUP_RUN",
            target_type="backup",
            target_id="b1",
            occurred_at=datetime(2026, 5, 22, 10, 0, 0),
        )

        selected = filter_audit_events(log.events, target_type="order")

        self.assertEqual([first], selected)
        self.assertEqual("ORDER_SUBMIT", log.query(action_code="ORDER_SUBMIT")[0].action_code)

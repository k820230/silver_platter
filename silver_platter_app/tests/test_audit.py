from datetime import datetime
from unittest import TestCase

from silver_platter.audit import (
    AuditLog,
    build_setting_change_detail,
    filter_audit_events,
)


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

    def test_append_records_actor_context(self):
        log = AuditLog()

        event = log.append(
            actor_type="user",
            user_id="u1",
            session_id="s1",
            source="web",
            action_code="SETTING_CHANGE",
            target_type="setting",
            target_id="risk",
            occurred_at=datetime(2026, 5, 22, 9, 0, 0),
        )

        self.assertEqual("u1", event.actor_id)
        self.assertEqual("u1", event.detail["actor_user_id"])
        self.assertEqual("s1", event.detail["actor_session_id"])
        self.assertEqual("web", event.detail["actor_source"])

    def test_build_setting_change_detail_records_only_changed_values(self):
        detail = build_setting_change_detail(
            {"max_order_krw": 100, "mode": "paper"},
            {"max_order_krw": 200, "mode": "paper", "kill_switch": True},
        )

        self.assertEqual("kill_switch,max_order_krw", detail["changed_keys"])
        self.assertIn('"max_order_krw": 100', detail["before"])
        self.assertIn('"max_order_krw": 200', detail["after"])
        self.assertIn('"kill_switch": true', detail["after"])

from datetime import datetime
from unittest import TestCase

from silver_platter.audit import (
    AuditLog,
    build_setting_change_detail,
    filter_audit_events,
    record_alert_user_action,
    record_risk_override,
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

    def test_append_masks_sensitive_detail(self):
        log = AuditLog()

        event = log.append(
            actor_type="system",
            actor_id="api",
            action_code="SECRET_TEST",
            target_type="config",
            detail={"api_key": "plain", "status": "ok"},
            occurred_at=datetime(2026, 5, 22, 9, 0, 0),
        )

        self.assertEqual("***", event.detail["api_key"])
        self.assertEqual("ok", event.detail["status"])

    def test_build_setting_change_detail_records_only_changed_values(self):
        detail = build_setting_change_detail(
            {"max_order_krw": 100, "mode": "paper"},
            {"max_order_krw": 200, "mode": "paper", "kill_switch": True},
        )

        self.assertEqual("kill_switch,max_order_krw", detail["changed_keys"])
        self.assertIn('"max_order_krw": 100', detail["before"])
        self.assertIn('"max_order_krw": 200', detail["after"])
        self.assertIn('"kill_switch": true', detail["after"])

    def test_records_alert_ack_and_risk_override_audit_events(self):
        log = AuditLog()

        alert_event = record_alert_user_action(
            log,
            alert_id="alert-1",
            action="ack",
            user_id="u1",
            occurred_at=datetime(2026, 5, 22, 9, 0, 0),
        )
        override_event = record_risk_override(
            log,
            override_id="override-1",
            user_id="u1",
            reason="manual review",
            scope="single_order",
            occurred_at=datetime(2026, 5, 22, 9, 1, 0),
        )

        self.assertEqual("ALERT_ACK", alert_event.action_code)
        self.assertEqual("RISK_OVERRIDE", override_event.action_code)
        self.assertEqual("manual review", override_event.detail["reason"])

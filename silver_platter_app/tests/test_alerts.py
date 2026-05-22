from datetime import datetime
from unittest import TestCase

from silver_platter.alerts import (
    InMemoryAlertDeliveryProvider,
    WebhookAlertDeliveryProvider,
    build_operations_alert_messages,
    build_realtime_alert_message,
    dispatch_alerts,
)
from silver_platter.audit import AuditLog
from silver_platter.headlines import RealtimeAlert
from silver_platter.operations import ComponentStatus, summarize_operations


class AlertsTests(TestCase):
    def test_build_operations_alert_messages_for_non_ok_components(self):
        checked_at = datetime(2026, 5, 22, 9, 0, 0)
        summary = summarize_operations(
            [
                ComponentStatus("api", "ok", "ready", checked_at),
                ComponentStatus("backup", "failed", "checksum mismatch", checked_at),
            ],
            generated_at=datetime(2026, 5, 22, 9, 1, 0),
        )

        messages = build_operations_alert_messages(summary)

        self.assertEqual(1, len(messages))
        self.assertEqual("critical", messages[0].severity)
        self.assertEqual("backup", messages[0].metadata["component"])
        self.assertIn("checksum mismatch", messages[0].body)

    def test_build_realtime_alert_message_preserves_market_risk_metadata(self):
        alert = RealtimeAlert(
            alert_id="geo-e1",
            severity="warning",
            message="international event volume shock detected",
            observed_at=datetime(2026, 5, 22, 10, 5, 0),
            volume_increase_pct=110.0,
            event_tags=("geopolitical", "sanction"),
        )

        message = build_realtime_alert_message(alert)

        self.assertEqual("geo-e1", message.alert_id)
        self.assertEqual("market_risk", message.channel)
        self.assertEqual("geopolitical,sanction", message.metadata["event_tags"])

    def test_dispatch_alerts_sends_and_records_audit(self):
        provider = InMemoryAlertDeliveryProvider()
        audit_log = AuditLog()
        summary = summarize_operations(
            [ComponentStatus("worker", "degraded", "lagging", datetime(2026, 5, 22, 9, 0, 0))],
            generated_at=datetime(2026, 5, 22, 9, 1, 0),
        )
        messages = build_operations_alert_messages(summary)

        results = dispatch_alerts(messages, [provider], audit_log)

        self.assertEqual(1, len(provider.messages))
        self.assertEqual("delivered", results[0].status)
        self.assertEqual("ALERT_DELIVER", audit_log.events[0].action_code)
        self.assertEqual("worker", provider.messages[0].metadata["component"])

    def test_webhook_provider_uses_injected_transport(self):
        calls = []

        def transport(url, headers, body):
            calls.append((url, headers, body))
            return {"ok": True}

        provider = WebhookAlertDeliveryProvider(
            "https://alerts.example.test",
            transport=transport,
        )
        summary = summarize_operations(
            [ComponentStatus("api", "critical", "down", datetime(2026, 5, 22, 9, 0, 0))],
            generated_at=datetime(2026, 5, 22, 9, 1, 0),
        )

        result = provider.send(build_operations_alert_messages(summary)[0])

        self.assertEqual("delivered", result.status)
        self.assertEqual("https://alerts.example.test", calls[0][0])
        self.assertEqual("ops-api-2026-05-22T09:00:00", calls[0][2]["alert_id"])

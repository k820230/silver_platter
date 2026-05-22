from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
import json
import urllib.request
from typing import Callable, Dict, Iterable, List, Optional

from silver_platter.audit import AuditLog
from silver_platter.headlines import RealtimeAlert
from silver_platter.operations import OperationsSummary


WebhookTransport = Callable[[str, Dict[str, str], Dict[str, object]], Dict[str, object]]


@dataclass(frozen=True)
class AlertDeliveryMessage:
    alert_id: str
    channel: str
    severity: str
    title: str
    body: str
    created_at: datetime
    target_uri: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "alert_id": self.alert_id,
            "channel": self.channel,
            "severity": self.severity,
            "title": self.title,
            "body": self.body,
            "created_at": self.created_at.isoformat(),
            "target_uri": self.target_uri,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class AlertDeliveryResult:
    provider_code: str
    alert_id: str
    status: str
    delivered_at: datetime
    error_message: str = ""

    def as_dict(self) -> dict:
        return {
            "provider_code": self.provider_code,
            "alert_id": self.alert_id,
            "status": self.status,
            "delivered_at": self.delivered_at.isoformat(),
            "error_message": self.error_message,
        }


class AlertDeliveryProvider(ABC):
    provider_code: str

    @abstractmethod
    def send(self, message: AlertDeliveryMessage) -> AlertDeliveryResult:
        raise NotImplementedError


class InMemoryAlertDeliveryProvider(AlertDeliveryProvider):
    def __init__(self, provider_code: str = "memory"):
        self.provider_code = provider_code
        self.messages: List[AlertDeliveryMessage] = []

    def send(self, message: AlertDeliveryMessage) -> AlertDeliveryResult:
        self.messages.append(message)
        return AlertDeliveryResult(
            provider_code=self.provider_code,
            alert_id=message.alert_id,
            status="delivered",
            delivered_at=datetime.utcnow(),
        )


class WebhookAlertDeliveryProvider(AlertDeliveryProvider):
    def __init__(
        self,
        webhook_url: str,
        provider_code: str = "webhook",
        transport: Optional[WebhookTransport] = None,
    ):
        if not webhook_url.strip():
            raise ValueError("webhook_url is required")
        self.webhook_url = webhook_url
        self.provider_code = provider_code
        self.transport = transport or _post_json

    def send(self, message: AlertDeliveryMessage) -> AlertDeliveryResult:
        try:
            response = self.transport(
                self.webhook_url,
                {"content-type": "application/json"},
                message.as_dict(),
            )
            status = "delivered" if response.get("ok", True) else "failed"
            error = "" if status == "delivered" else str(response.get("error", "failed"))
        except Exception as exc:
            status = "failed"
            error = str(exc)
        return AlertDeliveryResult(
            provider_code=self.provider_code,
            alert_id=message.alert_id,
            status=status,
            delivered_at=datetime.utcnow(),
            error_message=error,
        )


def _post_json(
    url: str,
    headers: Dict[str, str],
    body: Dict[str, object],
) -> Dict[str, object]:
    payload = json.dumps(body, ensure_ascii=True, sort_keys=True).encode("utf-8")
    request = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=5) as response:
        response_body = response.read().decode("utf-8")
    if not response_body:
        return {"ok": True}
    return json.loads(response_body)


def build_operations_alert_messages(
    summary: OperationsSummary,
    channel: str = "operations",
) -> List[AlertDeliveryMessage]:
    messages = []
    for component in summary.components:
        if component.status in {"ok", "pass", "ready"}:
            continue
        severity = (
            "critical"
            if component.status in {"failed", "critical", "block"}
            else "warning"
        )
        messages.append(
            AlertDeliveryMessage(
                alert_id="ops-%s-%s" % (component.component, component.checked_at.isoformat()),
                channel=channel,
                severity=severity,
                title="%s status is %s" % (component.component, component.status),
                body=component.detail,
                created_at=summary.generated_at,
                metadata={
                    "component": component.component,
                    "status": component.status,
                },
            )
        )
    return messages


def build_realtime_alert_message(
    alert: RealtimeAlert,
    channel: str = "market_risk",
) -> AlertDeliveryMessage:
    return AlertDeliveryMessage(
        alert_id=alert.alert_id,
        channel=channel,
        severity=alert.severity,
        title=alert.message,
        body="volume increase %.4f%%" % alert.volume_increase_pct,
        created_at=alert.observed_at,
        metadata={
            "event_tags": ",".join(alert.event_tags),
            "volume_increase_pct": str(alert.volume_increase_pct),
        },
    )


def dispatch_alerts(
    messages: Iterable[AlertDeliveryMessage],
    providers: Iterable[AlertDeliveryProvider],
    audit_log: Optional[AuditLog] = None,
) -> List[AlertDeliveryResult]:
    results = []
    for message in messages:
        for provider in providers:
            result = provider.send(message)
            results.append(result)
            if audit_log is not None:
                audit_log.append(
                    actor_type="system",
                    actor_id=provider.provider_code,
                    action_code="ALERT_DELIVER",
                    target_type="alert",
                    target_id=message.alert_id,
                    detail={
                        "status": result.status,
                        "severity": message.severity,
                        "channel": message.channel,
                        "provider_code": provider.provider_code,
                        "error_message": result.error_message,
                    },
                    occurred_at=result.delivered_at,
                )
    return results

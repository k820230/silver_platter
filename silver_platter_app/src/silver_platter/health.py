from dataclasses import dataclass
import socket
from typing import Dict

from silver_platter.config import AppSettings


@dataclass(frozen=True)
class ComponentHealth:
    status: str
    detail: str

    def as_dict(self) -> Dict[str, str]:
        return {"status": self.status, "detail": self.detail}


def ping_goldilocks(settings: AppSettings) -> ComponentHealth:
    goldilocks = settings.goldilocks
    try:
        with socket.create_connection(
            (goldilocks.host, goldilocks.port),
            timeout=goldilocks.connect_timeout_seconds,
        ):
            return ComponentHealth("ok", "tcp connection succeeded")
    except OSError as exc:
        return ComponentHealth("degraded", "tcp connection failed: %s" % exc)


def get_health(settings: AppSettings) -> Dict[str, object]:
    goldilocks = ping_goldilocks(settings)
    overall = "ok" if goldilocks.status == "ok" else "degraded"
    return {
        "status": overall,
        "components": {
            "goldilocks": goldilocks.as_dict(),
        },
        "settings": settings.redacted(),
    }

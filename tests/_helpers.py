"""Shared test doubles."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.mqtt_bridge import ListenerStatus


@dataclass
class FakeBridge:
    """In-memory MqttBridge for tests. Records published messages instead of
    talking to a broker."""

    published: list[dict[str, Any]] = field(default_factory=list)
    _status: ListenerStatus | None = None
    _status_log: list[ListenerStatus] = field(default_factory=list)
    raise_on_publish: Exception | None = None

    def publish(self, topic: str, payload: bytes, *, qos: int = 1, retain: bool = False) -> None:
        if self.raise_on_publish is not None:
            raise self.raise_on_publish
        self.published.append({"topic": topic, "payload": payload, "qos": qos, "retain": retain})

    @property
    def listener_status(self) -> ListenerStatus | None:
        return self._status

    def set_status(self, status: ListenerStatus | None) -> None:
        self._status = status
        if status is not None:
            self._status_log.insert(0, status)

    def status_log(self) -> list[ListenerStatus]:
        return list(self._status_log)

    def disconnect(self) -> None:
        pass

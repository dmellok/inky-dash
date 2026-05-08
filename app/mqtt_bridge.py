"""MQTT publisher + listener-status subscriber.

The wire format is frozen (v4-brief §"MQTT contract — frozen interface"). This
module is the only place that talks to the broker. ``MqttBridge`` is a
``Protocol`` so tests can substitute a fake without touching paho-mqtt.

If MQTT_HOST isn't set, the app boots with a ``NullBridge`` — pushes raise a
clear "MQTT not configured" error instead of silently dropping.
"""

from __future__ import annotations

import collections
import json
import logging
import threading
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

logger = logging.getLogger(__name__)

# How many recent inky/status messages to keep around for the debug log.
STATUS_LOG_CAPACITY = 50


@dataclass(frozen=True)
class ListenerStatus:
    state: str  # "rendering" | "idle" | "offline" | "unknown"
    raw: dict[str, Any]
    received_at: datetime


@runtime_checkable
class MqttBridge(Protocol):
    """The contract PushManager depends on. Implementations: Paho or Null."""

    def publish(
        self, topic: str, payload: bytes, *, qos: int = 1, retain: bool = False
    ) -> None: ...

    @property
    def listener_status(self) -> ListenerStatus | None: ...

    def status_log(self) -> list[ListenerStatus]:
        """Recent inky/status messages, newest-first. Bounded ring buffer."""
        ...

    def disconnect(self) -> None: ...


class NullBridge:
    """Used when MQTT isn't configured. Pushes fail loudly; status is None."""

    def publish(self, topic: str, payload: bytes, *, qos: int = 1, retain: bool = False) -> None:
        raise RuntimeError("MQTT not configured; set MQTT_HOST to enable push")

    @property
    def listener_status(self) -> ListenerStatus | None:
        return None

    def status_log(self) -> list[ListenerStatus]:
        return []

    def disconnect(self) -> None:
        pass


class PahoBridge:
    """paho-mqtt-backed bridge. Connects on construction, subscribes to status,
    publishes on demand. Calls ``loop_start()`` so the network loop runs in a
    background thread."""

    def __init__(
        self,
        *,
        host: str,
        port: int = 1883,
        username: str | None = None,
        password: str | None = None,
        status_topic: str = "inky/status",
        client_id: str = "inky-dash-companion",
    ) -> None:
        self._status_topic = status_topic
        self._lock = threading.Lock()
        self._latest_status: ListenerStatus | None = None
        self._status_log: collections.deque[ListenerStatus] = collections.deque(
            maxlen=STATUS_LOG_CAPACITY
        )

        self._client = mqtt.Client(
            callback_api_version=CallbackAPIVersion.VERSION2,
            client_id=client_id,
        )
        if username:
            self._client.username_pw_set(username, password)

        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message

        self._client.connect(host, port, keepalive=60)
        self._client.loop_start()

    def _on_connect(
        self, client: mqtt.Client, _userdata: Any, _flags: Any, rc: Any, _props: Any = None
    ) -> None:
        # rc is ReasonCode in v2 callback API
        logger.info("MQTT connected (rc=%s); subscribing to %s", rc, self._status_topic)
        client.subscribe(self._status_topic, qos=1)

    def _on_message(self, _client: mqtt.Client, _userdata: Any, msg: mqtt.MQTTMessage) -> None:
        if msg.topic != self._status_topic:
            return
        try:
            raw = json.loads(msg.payload.decode())
        except (json.JSONDecodeError, UnicodeDecodeError) as err:
            logger.warning("Could not parse listener status payload: %s", err)
            return
        if not isinstance(raw, dict):
            return
        state = str(raw.get("state", "unknown"))
        status = ListenerStatus(
            state=state,
            raw=raw,
            received_at=datetime.now(UTC),
        )
        with self._lock:
            self._latest_status = status
            self._status_log.appendleft(status)

    def publish(self, topic: str, payload: bytes, *, qos: int = 1, retain: bool = False) -> None:
        info = self._client.publish(topic, payload, qos=qos, retain=retain)
        # Paho's queue-while-disconnected behaviour creates a thorny
        # rc/published mismatch:
        #   1. publish() is called; client isn't connected yet.
        #   2. Message gets queued, info.rc set to MQTT_ERR_NO_CONN.
        #   3. Network thread reconnects, flushes the queue, broker acks.
        #   4. Paho sets info._published = True but NEVER updates info.rc.
        # So `info.is_published()` and `info.wait_for_publish()` both raise
        # "The client is not currently connected" off that stale rc, even
        # though the message actually made it. Read the underlying
        # `_published` flag directly to get the real outcome.
        deadline = time.monotonic() + 10
        while not info._published and time.monotonic() < deadline:
            time.sleep(0.05)
        if not info._published:
            raise RuntimeError(
                f"MQTT publish timed out after 10s "
                f"(initial rc={info.rc}: {mqtt.error_string(info.rc)})"
            )

    @property
    def listener_status(self) -> ListenerStatus | None:
        with self._lock:
            return self._latest_status

    def status_log(self) -> list[ListenerStatus]:
        with self._lock:
            return list(self._status_log)

    def disconnect(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()

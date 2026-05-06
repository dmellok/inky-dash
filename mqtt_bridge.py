from __future__ import annotations

import json
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import paho.mqtt.client as mqtt

from config import Config


@dataclass
class StatusSnapshot:
    online: bool
    stale: bool
    state: str | None
    ts: str | None
    last_url: str | None
    last_result: str | None
    last_render_at: str | None
    last_duration_s: float | None
    received_at: str | None
    seconds_since_message: float | None
    log_tail: list[str]


def _iso(epoch: float | None) -> str | None:
    if epoch is None:
        return None
    return (
        datetime.fromtimestamp(epoch, tz=timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


class MqttBridge:
    """Bridge to the on-Pi listener.

    Publishes inky/update; subscribes to inky/status (retained, LWT-empty = offline)
    and inky/log (plaintext, last N buffered for the UI).
    """

    def __init__(self, config: Config):
        self.config = config
        self._lock = threading.Lock()
        self._last_status: dict[str, Any] | None = None
        self._status_received_at: float | None = None
        self._listener_offline = True
        self._log: deque[str] = deque(maxlen=config.log_buffer_size)

        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=config.mqtt_client_id,
        )
        if config.mqtt_username:
            self._client.username_pw_set(config.mqtt_username, config.mqtt_password or "")
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

    def start(self) -> None:
        self._note(f"connecting to {self.config.mqtt_host}:{self.config.mqtt_port}")
        try:
            self._client.connect_async(
                self.config.mqtt_host, self.config.mqtt_port, keepalive=60
            )
            self._client.loop_start()
        except Exception as exc:
            self._note(f"connect failed: {exc}")

    def stop(self) -> None:
        self._client.loop_stop()
        try:
            self._client.disconnect()
        except Exception:
            pass

    def publish_update(self, payload: dict[str, Any]) -> mqtt.MQTTMessageInfo:
        body = json.dumps(payload, separators=(",", ":"))
        return self._client.publish(
            self.config.topic_update, body, qos=1, retain=False
        )

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            now = time.time()
            since = (now - self._status_received_at) if self._status_received_at else None
            stale = since is not None and since > self.config.status_stale_seconds
            data = self._last_status or {}
            snap = StatusSnapshot(
                online=not self._listener_offline,
                stale=bool(stale),
                state=data.get("state"),
                ts=data.get("ts"),
                last_url=data.get("last_url"),
                last_result=data.get("last_result"),
                last_render_at=data.get("last_render_at"),
                last_duration_s=data.get("last_duration_s"),
                received_at=_iso(self._status_received_at),
                seconds_since_message=since,
                log_tail=list(self._log),
            )
        return snap.__dict__

    def _note(self, line: str) -> None:
        with self._lock:
            self._log.append(f"[mqtt] {line}")

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if getattr(reason_code, "is_failure", False):
            self._note(f"connect failed: {reason_code}")
            return
        client.subscribe(
            [(self.config.topic_status, 1), (self.config.topic_log, 0)]
        )
        self._note("connected")

    def _on_disconnect(self, client, userdata, flags=None, reason_code=None, properties=None):
        self._note(f"disconnected (rc={reason_code})")

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        if topic == self.config.topic_status:
            self._handle_status(msg.payload)
        elif topic == self.config.topic_log:
            try:
                text = msg.payload.decode("utf-8", errors="replace").rstrip()
            except Exception:
                text = repr(msg.payload)
            with self._lock:
                self._log.append(text)

    def _handle_status(self, payload: bytes) -> None:
        with self._lock:
            self._status_received_at = time.time()
            if not payload:
                # LWT empty payload => listener offline
                self._listener_offline = True
                self._last_status = None
                return
            self._listener_offline = False
            try:
                self._last_status = json.loads(payload.decode("utf-8"))
            except Exception:
                self._last_status = None
                self._log.append(f"[mqtt] bad status payload: {payload!r}")

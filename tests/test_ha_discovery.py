"""Tests for the HA autodiscovery config payload builders + the
HomeAssistantDiscovery class lifecycle.

These exercise the pure config-shape functions directly (no broker) and
use a fake bridge to verify the start/stop/republish lifecycle publishes
to the expected topics with the expected retain semantics.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from dataclasses import dataclass

import pytest

from app.ha_discovery import (
    AVAILABILITY_TOPIC,
    CMD_TOPIC_ACTIVE_PAGE,
    CMD_TOPIC_PUSH_PAGE,
    STATE_TOPIC_BUSY,
    STATE_TOPIC_IMAGE_URL,
    STATE_TOPIC_LAST_ERROR,
    STATE_TOPIC_LAST_PUSH,
    STATE_TOPIC_PUSH_COUNT,
    HomeAssistantDiscovery,
    build_button_config,
    build_diagnostic_configs,
    build_image_config,
    build_select_config,
)
from app.mqtt_bridge import SubscribeHandler
from app.push import PushResult

# -- Fakes ---------------------------------------------------------------


@dataclass
class _Pub:
    topic: str
    payload: bytes
    qos: int
    retain: bool


class _FakeBridge:
    """Stub MqttBridge that records every publish + holds subscriber refs."""

    def __init__(self) -> None:
        self.published: list[_Pub] = []
        self.subscriptions: dict[str, SubscribeHandler] = {}
        self.lock = threading.Lock()

    def publish(self, topic: str, payload: bytes, *, qos: int = 1, retain: bool = False) -> None:
        with self.lock:
            self.published.append(_Pub(topic, payload, qos, retain))

    def subscribe(self, topic: str, handler: SubscribeHandler, *, qos: int = 1) -> None:
        self.subscriptions[topic] = handler

    @property
    def listener_status(self) -> None:
        return None

    def status_log(self) -> list[object]:
        return []

    def disconnect(self) -> None:
        pass

    def topics(self) -> list[str]:
        return [p.topic for p in self.published]

    def payload_for(self, topic: str) -> dict[str, object]:
        for p in reversed(self.published):
            if p.topic == topic:
                return json.loads(p.payload.decode())
        raise AssertionError(f"no publish to {topic}")

    def str_payload_for(self, topic: str) -> str:
        for p in reversed(self.published):
            if p.topic == topic:
                return p.payload.decode()
        raise AssertionError(f"no publish to {topic}")


class _FakePushManager:
    def __init__(self) -> None:
        self.pushes: list[str] = []
        self.listeners: list[Callable[[PushResult], None]] = []

    def add_listener(self, cb: Callable[[PushResult], None]) -> None:
        self.listeners.append(cb)

    def remove_listener(self, cb: Callable[[PushResult], None]) -> None:
        if cb in self.listeners:
            self.listeners.remove(cb)

    def push(self, page_id: str, **kwargs: object) -> PushResult:
        self.pushes.append(page_id)
        result = PushResult(
            status="sent",
            digest="abc123",
            url="http://example.test/renders/abc123.png",
        )
        # Mimic real PushManager — fire listeners after a push.
        for cb in list(self.listeners):
            cb(result)
        return result


@dataclass
class _StubPage:
    id: str
    name: str


class _FakePageStore:
    def __init__(self, pages: list[_StubPage]) -> None:
        self._pages = list(pages)
        self.listeners: list[Callable[[], None]] = []

    def all(self) -> list[_StubPage]:
        return list(self._pages)

    def add_listener(self, cb: Callable[[], None]) -> None:
        self.listeners.append(cb)

    def remove_listener(self, cb: Callable[[], None]) -> None:
        if cb in self.listeners:
            self.listeners.remove(cb)

    def replace(self, pages: list[_StubPage]) -> None:
        self._pages = list(pages)
        for cb in list(self.listeners):
            cb()


# -- Config-builder unit tests -------------------------------------------


def test_button_config_shape() -> None:
    topic, payload = build_button_config("good-morning", "Good Morning", base_url="http://x")
    assert topic == "homeassistant/button/inky_dash/page_good-morning/config"
    assert payload["name"] == "Good Morning"
    assert payload["unique_id"] == "inky_dash_page_good-morning"
    assert payload["command_topic"] == CMD_TOPIC_PUSH_PAGE
    assert payload["payload_press"] == "good-morning"
    # Every entity must share the same device identifiers so HA groups them.
    assert payload["device"]["identifiers"] == ["inky_dash"]


def test_select_config_lists_page_ids() -> None:
    _, payload = build_select_config(["a", "b"], base_url="http://x")
    assert payload["options"] == ["a", "b"]
    # Empty list must not produce zero options (HA rejects the config).
    _, empty = build_select_config([], base_url="http://x")
    assert empty["options"] == [""]


def test_image_config_uses_url_topic() -> None:
    topic, payload = build_image_config(base_url="http://x")
    assert topic == "homeassistant/image/inky_dash/last_render/config"
    assert payload["url_topic"] == STATE_TOPIC_IMAGE_URL
    assert "image_encoding" not in payload  # url_topic mode doesn't take it


def test_diagnostic_configs_cover_every_sensor() -> None:
    configs = build_diagnostic_configs(base_url="http://x")
    topics = [t for t, _ in configs]
    assert "homeassistant/sensor/inky_dash/last_push/config" in topics
    assert "homeassistant/sensor/inky_dash/push_count_today/config" in topics
    assert "homeassistant/sensor/inky_dash/last_error/config" in topics
    assert "homeassistant/binary_sensor/inky_dash/busy/config" in topics
    # Every diagnostic should be entity_category=diagnostic.
    for _, payload in configs:
        assert payload["entity_category"] == "diagnostic"


# -- Lifecycle tests -----------------------------------------------------


@pytest.fixture
def harness() -> tuple[_FakeBridge, _FakePushManager, _FakePageStore, HomeAssistantDiscovery]:
    bridge = _FakeBridge()
    pm = _FakePushManager()
    store = _FakePageStore([_StubPage("good-morning", "Good Morning"), _StubPage("cyber", "Cyber")])
    disco = HomeAssistantDiscovery(
        bridge=bridge,  # type: ignore[arg-type]
        push_manager=pm,  # type: ignore[arg-type]
        page_store=store,  # type: ignore[arg-type]
        base_url="http://inky.lan",
    )
    return bridge, pm, store, disco


def test_start_publishes_availability_online_and_every_entity_config(
    harness: tuple[_FakeBridge, _FakePushManager, _FakePageStore, HomeAssistantDiscovery],
) -> None:
    bridge, pm, store, disco = harness
    disco.start()

    # Availability ON, retained.
    avail = next(p for p in bridge.published if p.topic == AVAILABILITY_TOPIC)
    assert avail.payload == b"online"
    assert avail.retain is True

    # Button for each page.
    assert any("/page_good-morning/config" in t for t in bridge.topics())
    assert any("/page_cyber/config" in t for t in bridge.topics())

    # Select + image + 4 diagnostic configs.
    expected = [
        "homeassistant/select/inky_dash/active_page/config",
        "homeassistant/image/inky_dash/last_render/config",
        "homeassistant/sensor/inky_dash/last_push/config",
        "homeassistant/sensor/inky_dash/push_count_today/config",
        "homeassistant/sensor/inky_dash/last_error/config",
        "homeassistant/binary_sensor/inky_dash/busy/config",
    ]
    for topic in expected:
        assert topic in bridge.topics(), f"missing publish to {topic}"

    # Subscribed to the two command topics.
    assert CMD_TOPIC_PUSH_PAGE in bridge.subscriptions
    assert CMD_TOPIC_ACTIVE_PAGE in bridge.subscriptions

    # Registered as a push listener so we get notified on real pushes.
    assert disco._on_push_result in pm.listeners

    # Registered as a page-store listener so add/remove of pages re-publishes.
    assert disco._on_pages_changed in store.listeners


def test_start_is_idempotent(
    harness: tuple[_FakeBridge, _FakePushManager, _FakePageStore, HomeAssistantDiscovery],
) -> None:
    bridge, _pm, _store, disco = harness
    disco.start()
    n = len(bridge.published)
    disco.start()  # second call — should no-op (already started flag set)
    assert len(bridge.published) == n


def test_stop_publishes_offline_and_empty_configs(
    harness: tuple[_FakeBridge, _FakePushManager, _FakePageStore, HomeAssistantDiscovery],
) -> None:
    bridge, pm, store, disco = harness
    disco.start()
    bridge.published.clear()  # reset to focus on stop()'s output

    disco.stop()

    # Empty payload on every per-page button config → HA deletes the entity.
    for page_id in ("good-morning", "cyber"):
        match = next(
            (p for p in bridge.published if p.topic.endswith(f"page_{page_id}/config")),
            None,
        )
        assert match is not None
        assert match.payload == b""
        assert match.retain is True

    # Empty on select + image + diagnostic configs too.
    for topic in (
        "homeassistant/select/inky_dash/active_page/config",
        "homeassistant/image/inky_dash/last_render/config",
        "homeassistant/sensor/inky_dash/last_push/config",
    ):
        match = next((p for p in bridge.published if p.topic == topic), None)
        assert match is not None and match.payload == b""

    # Availability OFFLINE retained.
    avail = next(p for p in reversed(bridge.published) if p.topic == AVAILABILITY_TOPIC)
    assert avail.payload == b"offline" and avail.retain is True

    # Listeners detached so a post-stop push doesn't fire.
    assert disco._on_push_result not in pm.listeners
    assert disco._on_pages_changed not in store.listeners


def test_push_command_routes_to_push_manager(
    harness: tuple[_FakeBridge, _FakePushManager, _FakePageStore, HomeAssistantDiscovery],
) -> None:
    bridge, pm, _store, disco = harness
    disco.start()

    handler = bridge.subscriptions[CMD_TOPIC_PUSH_PAGE]
    handler(CMD_TOPIC_PUSH_PAGE, b"good-morning")

    assert pm.pushes == ["good-morning"]
    # PushResult listener should have fired — image URL + push count published.
    assert bridge.str_payload_for(STATE_TOPIC_IMAGE_URL) == (
        "http://example.test/renders/abc123.png"
    )
    assert bridge.str_payload_for(STATE_TOPIC_PUSH_COUNT) == "1"


def test_push_count_resets_per_utc_day(
    harness: tuple[_FakeBridge, _FakePushManager, _FakePageStore, HomeAssistantDiscovery],
) -> None:
    _bridge, pm, _store, disco = harness
    disco.start()
    # Two successful pushes today → count = 2.
    result = PushResult(status="sent", digest="x", url="http://x/renders/x.png")
    disco._on_push_result(result)
    disco._on_push_result(result)
    assert disco._push_count == 2
    # Simulate the next UTC day rolling over.
    disco._push_count_day = "1970-01-01"
    disco._on_push_result(result)
    assert disco._push_count == 1


def test_failed_push_publishes_last_error_only(
    harness: tuple[_FakeBridge, _FakePushManager, _FakePageStore, HomeAssistantDiscovery],
) -> None:
    bridge, _pm, _store, disco = harness
    disco.start()
    disco._on_push_result(PushResult(status="failed", error="render: boom"))
    assert bridge.str_payload_for(STATE_TOPIC_LAST_ERROR) == "render: boom"
    # last_push timestamp should NOT have been updated on a failure.
    publishes_to_last_push = [p for p in bridge.published if p.topic == STATE_TOPIC_LAST_PUSH]
    assert publishes_to_last_push == []


def test_active_page_command_pushes_AND_echoes_state(
    harness: tuple[_FakeBridge, _FakePushManager, _FakePageStore, HomeAssistantDiscovery],
) -> None:
    bridge, pm, _store, disco = harness
    disco.start()

    handler = bridge.subscriptions[CMD_TOPIC_ACTIVE_PAGE]
    handler(CMD_TOPIC_ACTIVE_PAGE, b"cyber")

    assert pm.pushes == ["cyber"]
    # State echoed back so HA's select reflects the new value.
    assert bridge.str_payload_for("inky/inky_dash/state/active_page") == "cyber"


def test_pages_changed_republishes_buttons_and_drops_stale(
    harness: tuple[_FakeBridge, _FakePushManager, _FakePageStore, HomeAssistantDiscovery],
) -> None:
    bridge, _pm, store, disco = harness
    disco.start()
    # User deletes "cyber" from /editor — page-store listener fires.
    store.replace([_StubPage("good-morning", "Good Morning")])

    # The cyber-button discovery config should have been re-published as empty
    # (delete-entity) since it's no longer a known page.
    cyber_deletes = [
        p for p in bridge.published if p.topic.endswith("page_cyber/config") and p.payload == b""
    ]
    assert len(cyber_deletes) >= 1
    # And good-morning's button config should have been re-published as a valid
    # non-empty config (it survived).
    gm_publishes = [
        p
        for p in bridge.published
        if p.topic.endswith("page_good-morning/config") and p.payload != b""
    ]
    assert len(gm_publishes) >= 2  # initial + republish


def test_busy_flag_flicks_on_during_ha_initiated_push(
    harness: tuple[_FakeBridge, _FakePushManager, _FakePageStore, HomeAssistantDiscovery],
) -> None:
    bridge, _pm, _store, disco = harness
    disco.start()
    bridge.published.clear()

    handler = bridge.subscriptions[CMD_TOPIC_PUSH_PAGE]
    handler(CMD_TOPIC_PUSH_PAGE, b"good-morning")

    # Sequence of busy values published: 1 (start of cmd) then 0 (push done).
    busy_publishes = [p for p in bridge.published if p.topic == STATE_TOPIC_BUSY]
    busy_values = [p.payload for p in busy_publishes]
    assert b"1" in busy_values
    # Last busy publish should be off.
    assert busy_values[-1] == b"0"

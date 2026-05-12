"""Home Assistant MQTT autodiscovery integration.

Publishes retained config payloads under ``homeassistant/<component>/inky_dash/...``
so HA's MQTT integration auto-creates a device with:

  - **button** entities, one per saved dashboard, that fire ``PushManager.push()``
  - **select** entity listing every dashboard; setting it pushes that page
  - **image** entity pointing at the most-recent render URL
  - **sensor** + **binary_sensor** diagnostics: last push time, push count,
    last error, busy state

Reuses the broker already configured for ``inky/update`` — no second
connection. The discovery prefix is fixed to ``homeassistant`` (the HA
default); users with a custom prefix will need a setting later.

Lifecycle:
  - ``start()`` — publish availability=online + LWT, publish all configs +
    initial state, subscribe to command topics. Idempotent.
  - ``stop()`` — publish availability=offline, publish empty retained
    configs to remove entities, unregister listeners. Idempotent.
  - ``republish_entities()`` — called on page save/delete to refresh the
    per-dashboard button + select options.

mypy --strict applies to this module — see pyproject.toml.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.mqtt_bridge import MqttBridge
    from app.push import PushManager, PushResult
    from app.state.page_store import PageStore

logger = logging.getLogger(__name__)

# Topic structure. The "ha_" prefix on commands keeps them out of the way
# of the existing inky/update + inky/status traffic.
DISCOVERY_PREFIX = "homeassistant"
NODE_ID = "inky_dash"
AVAILABILITY_TOPIC = f"inky/{NODE_ID}/availability"
STATE_TOPIC_LAST_PUSH = f"inky/{NODE_ID}/state/last_push"
STATE_TOPIC_PUSH_COUNT = f"inky/{NODE_ID}/state/push_count_today"
STATE_TOPIC_LAST_ERROR = f"inky/{NODE_ID}/state/last_error"
STATE_TOPIC_BUSY = f"inky/{NODE_ID}/state/busy"
STATE_TOPIC_IMAGE_URL = f"inky/{NODE_ID}/state/image_url"
STATE_TOPIC_ACTIVE_PAGE = f"inky/{NODE_ID}/state/active_page"
CMD_TOPIC_PUSH_PAGE = f"inky/{NODE_ID}/cmd/push_page"
CMD_TOPIC_ACTIVE_PAGE = f"inky/{NODE_ID}/cmd/active_page"


def _device_info(base_url: str) -> dict[str, Any]:
    """The HA "device" registry entry every entity links into. All entities
    sharing identifiers=['inky_dash'] cluster under one device card in HA."""
    return {
        "identifiers": ["inky_dash"],
        "name": "Inky Dash",
        "manufacturer": "Pimoroni",
        "model": "Inky Impression",
        "sw_version": "v4",
        "configuration_url": base_url,
    }


def _discovery_topic(component: str, object_id: str) -> str:
    return f"{DISCOVERY_PREFIX}/{component}/{NODE_ID}/{object_id}/config"


def _availability_block() -> list[dict[str, str]]:
    """Shared availability spec — every entity references the same LWT."""
    return [
        {
            "topic": AVAILABILITY_TOPIC,
            "payload_available": "online",
            "payload_not_available": "offline",
        }
    ]


def build_button_config(
    page_id: str, page_name: str, *, base_url: str
) -> tuple[str, dict[str, Any]]:
    """Discovery payload for one push-this-dashboard button entity."""
    topic = _discovery_topic("button", f"page_{page_id}")
    payload = {
        "name": page_name,
        "unique_id": f"inky_dash_page_{page_id}",
        "object_id": f"inky_dash_page_{page_id}",
        "command_topic": CMD_TOPIC_PUSH_PAGE,
        "payload_press": page_id,
        "availability": _availability_block(),
        "device": _device_info(base_url),
        "icon": "mdi:image",
    }
    return topic, payload


def build_select_config(page_ids: list[str], *, base_url: str) -> tuple[str, dict[str, Any]]:
    """Discovery payload for the 'active dashboard' select entity."""
    topic = _discovery_topic("select", "active_page")
    payload = {
        "name": "Active dashboard",
        "unique_id": "inky_dash_active_page",
        "object_id": "inky_dash_active_page",
        "command_topic": CMD_TOPIC_ACTIVE_PAGE,
        "state_topic": STATE_TOPIC_ACTIVE_PAGE,
        "options": page_ids or [""],
        "availability": _availability_block(),
        "device": _device_info(base_url),
        "icon": "mdi:view-dashboard",
    }
    return topic, payload


def build_image_config(*, base_url: str) -> tuple[str, dict[str, Any]]:
    """Discovery payload for an `image` entity that follows the last render.

    Uses ``url_topic`` — the URL string is published whenever a push lands,
    and HA fetches the bytes. Cheaper than republishing the PNG itself.
    """
    topic = _discovery_topic("image", "last_render")
    payload = {
        "name": "Last render",
        "unique_id": "inky_dash_last_render",
        "object_id": "inky_dash_last_render",
        "url_topic": STATE_TOPIC_IMAGE_URL,
        "content_type": "image/png",
        "availability": _availability_block(),
        "device": _device_info(base_url),
    }
    return topic, payload


def build_diagnostic_configs(*, base_url: str) -> list[tuple[str, dict[str, Any]]]:
    """Four diagnostic entities: last_push timestamp, push_count_today, last_error, busy."""
    out: list[tuple[str, dict[str, Any]]] = []
    out.append(
        (
            _discovery_topic("sensor", "last_push"),
            {
                "name": "Last push",
                "unique_id": "inky_dash_last_push",
                "object_id": "inky_dash_last_push",
                "state_topic": STATE_TOPIC_LAST_PUSH,
                "device_class": "timestamp",
                "entity_category": "diagnostic",
                "availability": _availability_block(),
                "device": _device_info(base_url),
            },
        )
    )
    out.append(
        (
            _discovery_topic("sensor", "push_count_today"),
            {
                "name": "Pushes today",
                "unique_id": "inky_dash_push_count_today",
                "object_id": "inky_dash_push_count_today",
                "state_topic": STATE_TOPIC_PUSH_COUNT,
                "state_class": "total_increasing",
                "entity_category": "diagnostic",
                "availability": _availability_block(),
                "device": _device_info(base_url),
            },
        )
    )
    out.append(
        (
            _discovery_topic("sensor", "last_error"),
            {
                "name": "Last error",
                "unique_id": "inky_dash_last_error",
                "object_id": "inky_dash_last_error",
                "state_topic": STATE_TOPIC_LAST_ERROR,
                "entity_category": "diagnostic",
                "availability": _availability_block(),
                "device": _device_info(base_url),
            },
        )
    )
    out.append(
        (
            _discovery_topic("binary_sensor", "busy"),
            {
                "name": "Busy",
                "unique_id": "inky_dash_busy",
                "object_id": "inky_dash_busy",
                "state_topic": STATE_TOPIC_BUSY,
                "payload_on": "1",
                "payload_off": "0",
                "entity_category": "diagnostic",
                "availability": _availability_block(),
                "device": _device_info(base_url),
            },
        )
    )
    return out


class HomeAssistantDiscovery:
    """Publishes HA discovery configs + relays HA commands to PushManager.

    Threading: command callbacks fire on the MQTT network thread. They hand
    off to ``PushManager.push(...)`` which has its own lock, so this is safe.
    State publishes are best-effort — broker outages just mean stale sensors
    in HA, not a crashed app.
    """

    def __init__(
        self,
        *,
        bridge: MqttBridge,
        push_manager: PushManager,
        page_store: PageStore,
        base_url: str,
    ) -> None:
        self._bridge = bridge
        self._push_manager = push_manager
        self._page_store = page_store
        self._base_url = base_url.rstrip("/")
        self._started = False
        self._lock = threading.Lock()
        # Push-count is per-UTC-day. Stored in-memory; resets on app restart
        # (the metric is intended for "today" anyway).
        self._push_count_day = ""
        self._push_count = 0
        # Track which page-button configs we've published, so we can clean
        # up retained configs for pages the user has since deleted.
        self._published_button_ids: set[str] = set()

    # -- Lifecycle --------------------------------------------------------

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True
        logger.info("HA discovery: starting")
        # Availability online (retained — HA shows the device as available
        # straight away, and the broker re-sends the retained message to any
        # late-joining HA instance).
        self._publish_str(AVAILABILITY_TOPIC, "online", retain=True)
        self._publish_entity_configs()
        # Subscribe to command topics. Bridge.subscribe is replace-on-same-topic
        # so a re-start replaces the prior handler instead of stacking.
        self._bridge.subscribe(CMD_TOPIC_PUSH_PAGE, self._on_push_page_cmd)
        self._bridge.subscribe(CMD_TOPIC_ACTIVE_PAGE, self._on_active_page_cmd)
        # Hook the push pipeline so sensor state follows real pushes.
        self._push_manager.add_listener(self._on_push_result)
        # And the page store so add/remove of pages republishes buttons.
        self._page_store.add_listener(self._on_pages_changed)
        # Seed the diagnostic sensors so HA shows defined-but-empty values
        # immediately rather than "unknown".
        self._publish_str(STATE_TOPIC_PUSH_COUNT, str(self._push_count), retain=True)
        self._publish_str(STATE_TOPIC_LAST_ERROR, "", retain=True)
        self._publish_str(STATE_TOPIC_BUSY, "0", retain=True)

    def stop(self) -> None:
        with self._lock:
            if not self._started:
                return
            self._started = False
        logger.info("HA discovery: stopping")
        # Detach hooks first so an in-flight push doesn't fire after stop().
        self._push_manager.remove_listener(self._on_push_result)
        self._page_store.remove_listener(self._on_pages_changed)
        # Remove every entity by publishing empty retained configs. HA reads
        # the empty payload as "delete this entity".
        for object_id_kind in self._every_object_id_kind():
            self._publish_str(_discovery_topic(*object_id_kind), "", retain=True)
        self._published_button_ids.clear()
        # Finally mark availability offline (retained).
        self._publish_str(AVAILABILITY_TOPIC, "offline", retain=True)

    def set_base_url(self, base_url: str) -> None:
        """Update the device's configuration_url + image base. Republishes
        configs if currently running so HA picks up the new URLs."""
        self._base_url = base_url.rstrip("/")
        if self._started:
            self._publish_entity_configs()

    # -- Hook handlers ----------------------------------------------------

    def _on_push_result(self, result: PushResult) -> None:
        """Called after every push attempt. Updates sensors + image URL."""
        try:
            now = datetime.now(UTC)
            iso = now.strftime("%Y-%m-%dT%H:%M:%S+00:00")
            if result.status == "sent":
                self._publish_str(STATE_TOPIC_LAST_PUSH, iso, retain=True)
                self._publish_str(STATE_TOPIC_LAST_ERROR, "", retain=True)
                if result.url:
                    self._publish_str(STATE_TOPIC_IMAGE_URL, result.url, retain=True)
                today = now.strftime("%Y-%m-%d")
                if today != self._push_count_day:
                    self._push_count_day = today
                    self._push_count = 0
                self._push_count += 1
                self._publish_str(STATE_TOPIC_PUSH_COUNT, str(self._push_count), retain=True)
            elif result.status == "failed" and result.error:
                self._publish_str(STATE_TOPIC_LAST_ERROR, result.error[:240], retain=True)
            # Busy is "did anything happen recently" — flick it on for the
            # length of a render so HA dashboards can show a spinner.
            self._publish_str(STATE_TOPIC_BUSY, "0", retain=True)
        except Exception:  # noqa: BLE001
            logger.exception("HA discovery: failed to publish push state")

    def _on_pages_changed(self) -> None:
        if not self._started:
            return
        try:
            self._publish_entity_configs()
        except Exception:  # noqa: BLE001
            logger.exception("HA discovery: failed to republish entity configs")

    def _on_push_page_cmd(self, _topic: str, payload: bytes) -> None:
        page_id = payload.decode("utf-8", errors="ignore").strip()
        if not page_id:
            return
        logger.info("HA discovery: HA requested push of page %r", page_id)
        # Tip the busy sensor on for the duration; _on_push_result flips it
        # back off when the push lands.
        self._publish_str(STATE_TOPIC_BUSY, "1", retain=True)
        try:
            self._push_manager.push(page_id)
        except Exception:  # noqa: BLE001
            # Listener will record the failure; we just need to release busy.
            self._publish_str(STATE_TOPIC_BUSY, "0", retain=True)
            raise

    def _on_active_page_cmd(self, topic: str, payload: bytes) -> None:
        # Select-entity command: same semantics as button press, plus echo
        # back to the select's state topic so HA shows the new value.
        page_id = payload.decode("utf-8", errors="ignore").strip()
        if not page_id:
            return
        self._publish_str(STATE_TOPIC_ACTIVE_PAGE, page_id, retain=True)
        self._on_push_page_cmd(topic, payload)

    # -- Discovery payload publishing -------------------------------------

    def _publish_entity_configs(self) -> None:
        """(Re)publish every discovery config based on current page state."""
        pages = self._page_store.all()
        seen_ids: set[str] = set()

        # One button per page.
        for page in pages:
            topic, payload = build_button_config(page.id, page.name, base_url=self._base_url)
            self._publish_json(topic, payload, retain=True)
            seen_ids.add(page.id)

        # Tear down buttons for pages that no longer exist.
        stale = self._published_button_ids - seen_ids
        for page_id in stale:
            self._publish_str(_discovery_topic("button", f"page_{page_id}"), "", retain=True)
        self._published_button_ids = seen_ids

        # Select entity.
        page_ids = sorted(p.id for p in pages)
        topic, payload = build_select_config(page_ids, base_url=self._base_url)
        self._publish_json(topic, payload, retain=True)

        # Image entity.
        topic, payload = build_image_config(base_url=self._base_url)
        self._publish_json(topic, payload, retain=True)

        # Diagnostic sensors.
        for topic, payload in build_diagnostic_configs(base_url=self._base_url):
            self._publish_json(topic, payload, retain=True)

    def _every_object_id_kind(self) -> list[tuple[str, str]]:
        """For stop() teardown — every (component, object_id) we've published."""
        out: list[tuple[str, str]] = []
        for page_id in self._published_button_ids:
            out.append(("button", f"page_{page_id}"))
        out.append(("select", "active_page"))
        out.append(("image", "last_render"))
        for object_id in ("last_push", "push_count_today", "last_error"):
            out.append(("sensor", object_id))
        out.append(("binary_sensor", "busy"))
        return out

    # -- Publish wrappers --------------------------------------------------

    def _publish_json(self, topic: str, payload: dict[str, Any], *, retain: bool = True) -> None:
        try:
            self._bridge.publish(
                topic, json.dumps(payload, sort_keys=True).encode("utf-8"), qos=1, retain=retain
            )
        except Exception:  # noqa: BLE001
            logger.warning("HA discovery: publish to %s failed", topic, exc_info=True)

    def _publish_str(self, topic: str, payload: str, *, retain: bool = False) -> None:
        try:
            self._bridge.publish(topic, payload.encode("utf-8"), qos=1, retain=retain)
        except Exception:  # noqa: BLE001
            logger.warning("HA discovery: publish to %s failed", topic, exc_info=True)

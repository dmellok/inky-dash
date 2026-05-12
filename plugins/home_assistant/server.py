"""Home Assistant entity tile.

Hits ``{base_url}/api/states/{entity_id}`` for each requested entity with a
long-lived access token. Returns a list of ``{entity_id, name, state, unit,
icon, kind}`` for the client to render.

Settings (set at /settings):
- ``base_url`` — your HA instance (e.g. ``http://homeassistant.local:8123``).
- ``token`` — a long-lived access token from your HA profile.

We deliberately do NOT cache state on disk because HA values change often
and the cell's refresh cadence is already throttled by the dashboard's
schedule cadence. A short in-memory failure cache exists for transport
errors so a flaky network doesn't blank the whole tile.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

# Phosphor icons keyed off the HA entity domain (the bit before the dot).
DOMAIN_ICONS: dict[str, str] = {
    "sensor": "ph-gauge",
    "binary_sensor": "ph-circle-half",
    "switch": "ph-power",
    "light": "ph-lightbulb",
    "lock": "ph-lock-key",
    "person": "ph-user",
    "device_tracker": "ph-map-pin",
    "climate": "ph-thermometer",
    "weather": "ph-cloud-sun",
    "media_player": "ph-music-notes",
    "cover": "ph-arrow-line-up",
    "fan": "ph-fan",
    "alarm_control_panel": "ph-shield-check",
}

# Device-class-specific icons (where they make sense). Beats the generic
# sensor icon for common cases like temperature/humidity.
DEVICE_CLASS_ICONS: dict[str, str] = {
    "temperature": "ph-thermometer",
    "humidity": "ph-drop",
    "battery": "ph-battery-medium",
    "power": "ph-lightning",
    "energy": "ph-lightning",
    "pressure": "ph-gauge",
    "co2": "ph-wind",
    "co": "ph-wind",
    "pm25": "ph-wind",
    "illuminance": "ph-sun",
    "door": "ph-door-open",
    "window": "ph-app-window",
    "motion": "ph-person-simple-walk",
    "occupancy": "ph-house",
    "smoke": "ph-fire",
    "moisture": "ph-drop-half",
}


def _icon_for(state: dict[str, Any]) -> str:
    domain = state["entity_id"].split(".", 1)[0]
    attrs = state.get("attributes") or {}
    dc = (attrs.get("device_class") or "").lower()
    return DEVICE_CLASS_ICONS.get(dc) or DOMAIN_ICONS.get(domain, "ph-circle")


def _format_state(state: dict[str, Any]) -> str:
    val = state.get("state")
    if val is None or val == "unknown" or val == "unavailable":
        return "—"
    return str(val)


def _split_entities(raw: str) -> list[str]:
    return [e.strip() for e in (raw or "").split(",") if e.strip()]


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    base_url = (settings.get("base_url") or "").strip().rstrip("/")
    token = (settings.get("token") or "").strip()
    if not base_url:
        return {"error": "Set the Home Assistant URL in plugin settings."}
    if not token:
        return {"error": "Set a long-lived access token in plugin settings."}

    entities = _split_entities(options.get("entities", ""))
    if not entities:
        return {"error": "Add at least one entity ID to the cell options."}

    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "inky-dash/1.0",
    }
    results: list[dict[str, Any]] = []
    failures: list[str] = []
    for entity_id in entities:
        url = f"{base_url}/api/states/{urllib.parse.quote(entity_id, safe='._-:')}"
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                state = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            failures.append(f"{entity_id}: HTTP {err.code}")
            continue
        except Exception as err:  # noqa: BLE001
            failures.append(f"{entity_id}: {type(err).__name__}")
            continue
        attrs = state.get("attributes") or {}
        results.append(
            {
                "entity_id": state.get("entity_id", entity_id),
                "name": attrs.get("friendly_name") or entity_id,
                "state": _format_state(state),
                "unit": attrs.get("unit_of_measurement") or "",
                "icon": _icon_for(state),
                "kind": (state.get("entity_id", entity_id).split(".", 1)[0]),
                "device_class": attrs.get("device_class") or "",
            }
        )

    # If we got nothing back, the user wants to see why — surface the first
    # error instead of pretending everything's fine.
    if not results and failures:
        return {"error": failures[0]}
    return {
        "entities": results,
        "errors": failures,  # partial failures show up as a hint in the UI
    }

"""App-level settings (MQTT broker config, companion base URL, panel hardware).

Stored at ``data/core/settings.json``. On first run, defaults are seeded from
env vars (``MQTT_HOST`` and friends) and persisted; after that the file is
authoritative and the UI is the way to change things.

Secrets are stored in plain JSON — the gitignored ``data/`` folder is the
trust boundary. If you put this on a multi-tenant box, encrypt the file.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_BASE_URL = "http://localhost:5555"
DEFAULT_ACCENT = "#b06750"  # warm dusty terracotta

Orientation = Literal["portrait", "landscape"]
Theme = Literal["light", "dark", "auto"]


class AppearanceSettings(BaseModel):
    """User-pickable look-and-feel.

    ``theme="auto"`` follows the OS's prefers-color-scheme. ``accent`` is a
    hex color (``#rrggbb``) used as the primary brand accent across the app.
    Both are applied client-side via inline JS in the appearance bootstrap
    so they take effect before first paint (no flash).
    """

    model_config = ConfigDict(extra="forbid")

    theme: Theme = "auto"
    accent: str = Field(
        default=DEFAULT_ACCENT,
        pattern=r"^#[0-9a-fA-F]{6}$",
        description="Primary accent color, hex (#rrggbb).",
    )


class PanelModelSpec(BaseModel):
    """Static descriptor for a panel SKU — its native (landscape) pixel grid."""

    model_config = ConfigDict(extra="forbid")
    label: str
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    palette: Literal["spectra_6", "acep_7"] = "spectra_6"


# Native pixel grids per spec sheet. All Inky Impression panels ship with the
# long edge as `width` (i.e. landscape native); the orientation setting picks
# the dashboard composition surface and decides whether to rotate the output
# byte stream before publishing.
PANEL_MODELS: dict[str, PanelModelSpec] = {
    "impression_4": PanelModelSpec(
        label='Inky Impression 4"', width=640, height=400, palette="acep_7"
    ),
    "impression_5_7": PanelModelSpec(
        label='Inky Impression 5.7"', width=600, height=448, palette="acep_7"
    ),
    "impression_7_3": PanelModelSpec(
        label='Inky Impression 7.3"', width=800, height=480, palette="acep_7"
    ),
    "spectra_6_7_3": PanelModelSpec(
        label='Inky Impression 7.3" (Spectra 6)', width=800, height=480, palette="spectra_6"
    ),
    "spectra_6_13_3": PanelModelSpec(
        label='Inky Impression 13.3" (Spectra 6)', width=1600, height=1200, palette="spectra_6"
    ),
}

DEFAULT_PANEL_MODEL = "spectra_6_13_3"


class PanelSettings(BaseModel):
    """Which physical panel we're driving + how it's mounted.

    Inky panels' native pixel buffer is *landscape* (e.g. 1600×1200 for the
    13.3" Spectra 6). When the panel is physically mounted on its side
    (``orientation="portrait"``), we compose the dashboard at the rotated
    dimensions and rotate the byte stream 90° before MQTT-publishing so it
    lands right-side-up on the panel's native pixel grid.
    """

    model_config = ConfigDict(extra="forbid")

    model: str = DEFAULT_PANEL_MODEL
    orientation: Orientation = "landscape"
    # Pixels to inset rendered content from each edge before publishing,
    # to compensate for a physical mat / bezel that occludes the outer
    # rim of the panel. The cropped-out area is filled with white at push
    # time. 0 disables the effect.
    underscan: int = Field(default=0, ge=0, le=200)

    def spec(self) -> PanelModelSpec:
        return PANEL_MODELS.get(self.model, PANEL_MODELS[DEFAULT_PANEL_MODEL])

    def render_dimensions(self) -> tuple[int, int]:
        """Composition viewport: landscape uses native; portrait swaps."""
        s = self.spec()
        if self.orientation == "landscape":
            return s.width, s.height
        return s.height, s.width

    def rotate_quarters(self) -> int:
        """How many 90° clockwise rotations to apply before publishing.

        Portrait composes at swapped dims (e.g. 1200×1600); we rotate CCW
        (quarters=3 ≡ -1 mod 4) to map onto the panel's native 1600×1200
        landscape grid the right way up — empirically the panel ends up
        upside-down with CW.
        """
        return 3 if self.orientation == "portrait" else 0


class MqttSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host: str = ""
    port: int = Field(default=1883, ge=1, le=65535)
    username: str = ""
    password: str = ""
    topic_update: str = "inky/update"
    topic_status: str = "inky/status"
    client_id: str = "inky-dash-companion"


class AuthSettings(BaseModel):
    """Single-shared-password gate on the admin UI + API.

    ``password_hash`` is a PBKDF2-HMAC-SHA256 hash of the password,
    stored as ``"pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>"`` so
    we can change iterations later without invalidating old hashes.
    Empty string means "no password set yet" — first boot lands on
    /setup to pick one.

    ``api_get_app_settings`` masks this field over the wire so it can't
    leak to the browser; the real value stays server-side.
    """

    model_config = ConfigDict(extra="forbid")

    password_hash: str = ""


class HomeAssistantSettings(BaseModel):
    """Home Assistant MQTT autodiscovery integration toggle.

    When ``enabled``, ``app.ha_discovery`` publishes retained config payloads
    to the broker so HA auto-creates a device with one button per saved
    dashboard, a select for the active page, an image entity for the most
    recent render, and diagnostic sensors. Reuses the broker already
    configured for ``inky/update``; no separate connection.
    """

    model_config = ConfigDict(extra="forbid")

    enabled: bool = False


class AppSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mqtt: MqttSettings = Field(default_factory=MqttSettings)
    base_url: str = DEFAULT_BASE_URL
    panel: PanelSettings = Field(default_factory=PanelSettings)
    appearance: AppearanceSettings = Field(default_factory=AppearanceSettings)
    ha: HomeAssistantSettings = Field(default_factory=HomeAssistantSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)


def initial_from_env() -> AppSettings:
    """Build settings from env vars — used to seed ``settings.json`` on first run."""
    return AppSettings(
        mqtt=MqttSettings(
            host=os.environ.get("MQTT_HOST", "") or "",
            port=int(os.environ.get("MQTT_PORT", "1883") or 1883),
            username=os.environ.get("MQTT_USERNAME", "") or "",
            password=os.environ.get("MQTT_PASSWORD", "") or "",
            topic_update=os.environ.get("MQTT_TOPIC_UPDATE", "inky/update"),
            topic_status=os.environ.get("MQTT_TOPIC_STATUS", "inky/status"),
        ),
        base_url=os.environ.get("COMPANION_BASE_URL", DEFAULT_BASE_URL),
    )


class AppSettingsStore:
    """Atomic JSON file for app-level settings."""

    FILENAME = "settings.json"

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> AppSettings:
        if not self.path.exists():
            return AppSettings()
        try:
            data = json.loads(self.path.read_text())
        except (json.JSONDecodeError, OSError):
            return AppSettings()
        try:
            return AppSettings.model_validate(data)
        except Exception:  # noqa: BLE001 — never crash the app on hand-edits
            return AppSettings()

    def save(self, settings: AppSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(settings.model_dump(mode="json"), indent=2, sort_keys=True))
        os.replace(tmp, self.path)

    def load_or_initialize(self) -> AppSettings:
        """Read the stored file if it exists; otherwise seed from env vars."""
        if self.path.exists():
            return self.load()
        seed = initial_from_env()
        # Persist so future runs don't keep re-reading env (and the UI can edit it).
        self.save(seed)
        return seed

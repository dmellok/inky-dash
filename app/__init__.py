from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from flask import Flask, abort, render_template, send_from_directory
from werkzeug.wrappers import Response

from app import admin, auth, composer, plugin_loader
from app.ha_discovery import HomeAssistantDiscovery
from app.mqtt_bridge import MqttBridge, NullBridge, PahoBridge
from app.push import PushManager
from app.scheduler import Scheduler
from app.state import (
    AppSettings,
    AppSettingsStore,
    Cell,
    HistoryStore,
    Page,
    PageStore,
    Panel,
    ScheduleStore,
    SettingsStore,
)

ROOT = Path(__file__).resolve().parent.parent
VERSION = (ROOT / "VERSION").read_text().strip()
DEFAULT_PLUGINS_DIR = ROOT / "plugins"
DEFAULT_DATA_ROOT = ROOT / "data"
PLUGIN_SCHEMA_PATH = ROOT / "schema" / "plugin.schema.json"
DEFAULT_BASE_URL = "http://localhost:5555"


_DEMO_PAGE = Page(
    id="_demo",
    name="Demo",
    panel=Panel(w=1600, h=1200),
    cells=[
        Cell(
            id="cell-1",
            x=0,
            y=0,
            w=1600,
            h=1200,
            plugin="clock",
            options={"format": "24h", "show_date": True},
        )
    ],
)


def build_bridge_from_settings(settings: AppSettings) -> MqttBridge:
    """Construct an MQTT bridge from app settings. NullBridge if no host."""
    if not settings.mqtt.host:
        return NullBridge()
    try:
        return PahoBridge(
            host=settings.mqtt.host,
            port=settings.mqtt.port,
            username=settings.mqtt.username or None,
            password=settings.mqtt.password or None,
            status_topic=settings.mqtt.topic_status,
            client_id=settings.mqtt.client_id,
        )
    except Exception:  # noqa: BLE001 — fall back so the app stays bootable
        return NullBridge()


def create_app(
    *,
    plugins_dir: Path | None = None,
    data_root: Path | None = None,
    bridge: MqttBridge | None = None,
    start_scheduler: bool | None = None,
) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(ROOT / "templates"),
        static_folder=str(ROOT / "static"),
    )

    plugins_path = plugins_dir or DEFAULT_PLUGINS_DIR
    data_path = data_root or DEFAULT_DATA_ROOT

    app.config["VERSION"] = VERSION
    app.config["PLUGINS_DIR"] = plugins_path
    app.config["DATA_ROOT"] = data_path

    # SECRET_KEY for Flask's signed-cookie session. Generated once per
    # install and persisted to data/core/.secret_key so sessions survive
    # restarts. See app.auth.load_or_create_secret_key for the file
    # format + perms (0600 best-effort).
    app.secret_key = auth.load_or_create_secret_key(data_path / "core")
    # Session cookie defaults: long-lived (sessions are a hobbyist
    # convenience, not a security boundary against in-browser theft),
    # http-only, lax samesite. Skip Secure since most home installs
    # are http-on-LAN.
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    )

    registry = plugin_loader.discover(
        plugins_path,
        schema_path=PLUGIN_SCHEMA_PATH,
        data_root=data_path / "plugins",
    )
    app.config["PLUGIN_REGISTRY"] = registry
    plugin_loader.register_routes(app, registry)

    page_store = PageStore(data_path / "core" / "pages.json")
    if not page_store.all():
        page_store.upsert(_DEMO_PAGE)
    app.config["PAGE_STORE"] = page_store

    # In-memory cache for editor live-preview: PUT /api/pages/<id>/preview
    # writes here, the composer reads from it before falling back to disk.
    app.config["PREVIEW_CACHE"] = {}

    app_settings_store = AppSettingsStore(data_path / "core" / "settings.json")
    app_settings = app_settings_store.load_or_initialize()
    app.config["APP_SETTINGS_STORE"] = app_settings_store

    # Install the single-shared-password auth gate. Public exceptions
    # (login / setup / static / /healthz / /renders/, plus loopback-only
    # access to /compose/<id>) live in app/auth.py. First boot lands on
    # /setup to pick a password.
    auth.install_gate(app, app_settings_store)

    # Source of truth: the panel settings (model + orientation) drive every
    # page's resolution. Sweep on boot so existing dashboards auto-align if
    # the user previously changed the panel out-of-band.
    from app.admin import _align_pages_to_panel

    _align_pages_to_panel(page_store, app_settings.panel)

    history = HistoryStore(data_path / "core" / "history.db")
    app.config["HISTORY_STORE"] = history

    settings_store = SettingsStore(data_path / "plugins")
    app.config["SETTINGS_STORE"] = settings_store

    renders_dir = data_path / "core" / "renders"
    app.config["RENDERS_DIR"] = renders_dir

    bridge_impl = bridge if bridge is not None else build_bridge_from_settings(app_settings)
    app.config["MQTT_BRIDGE"] = bridge_impl

    push_manager = PushManager(
        bridge=bridge_impl,
        history=history,
        page_store=page_store,
        renders_dir=renders_dir,
        base_url=app_settings.base_url,
        topic=app_settings.mqtt.topic_update,
        rotate_quarters=app_settings.panel.rotate_quarters(),
        underscan=app_settings.panel.underscan,
    )
    app.config["PUSH_MANAGER"] = push_manager

    # HA autodiscovery — opt-in via Settings → Home Assistant. Always
    # instantiated so the admin can flip it on/off without re-creating
    # objects, but only ``start()``-ed if currently enabled AND the
    # broker is real (not NullBridge — discovery configs would just
    # raise on every publish otherwise).
    ha_discovery = HomeAssistantDiscovery(
        bridge=bridge_impl,
        push_manager=push_manager,
        page_store=page_store,
        base_url=app_settings.base_url,
    )
    app.config["HA_DISCOVERY"] = ha_discovery
    if app_settings.ha.enabled and not isinstance(bridge_impl, NullBridge):
        ha_discovery.start()

    schedule_store = ScheduleStore(data_path / "core" / "schedules.json")
    app.config["SCHEDULE_STORE"] = schedule_store

    scheduler = Scheduler(store=schedule_store, push_manager=push_manager)
    app.config["SCHEDULER"] = scheduler
    # Auto-start the daemon thread unless we're in tests (where the
    # `start_scheduler=False` kwarg keeps things deterministic).
    should_start = start_scheduler if start_scheduler is not None else True
    if should_start:
        scheduler.start()

    app.register_blueprint(composer.bp)
    app.register_blueprint(admin.bp)

    @app.get("/renders/<digest>.png")
    def serve_render(digest: str) -> Response:
        # Constrain digest shape — the artifact filenames are 16-hex SHA256s.
        if len(digest) != 16 or not all(c in "0123456789abcdef" for c in digest):
            abort(404)
        return send_from_directory(renders_dir, f"{digest}.png")

    @app.get("/")
    def index() -> str:
        return render_template("index.html")

    @app.get("/healthz")
    def healthz() -> dict[str, object]:
        return {
            "status": "ok",
            "version": VERSION,
            "plugins": {
                "loaded": sorted(registry.plugins.keys()),
                "errors": [{"id": e.plugin_id, "message": e.message} for e in registry.errors],
            },
            "mqtt": {
                "connected": not isinstance(bridge_impl, NullBridge),
            },
        }

    return app

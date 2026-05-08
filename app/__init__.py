from __future__ import annotations

from pathlib import Path

from flask import Flask, abort, render_template, send_from_directory
from werkzeug.wrappers import Response

from app import admin, composer, plugin_loader
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
    )
    app.config["PUSH_MANAGER"] = push_manager

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

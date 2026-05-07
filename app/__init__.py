from __future__ import annotations

from pathlib import Path

from flask import Flask

from app import admin, composer, plugin_loader
from app.state import Cell, Page, PageStore, Panel

ROOT = Path(__file__).resolve().parent.parent
VERSION = (ROOT / "VERSION").read_text().strip()
DEFAULT_PLUGINS_DIR = ROOT / "plugins"
DEFAULT_DATA_ROOT = ROOT / "data"
PLUGIN_SCHEMA_PATH = ROOT / "schema" / "plugin.schema.json"


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


def create_app(
    *,
    plugins_dir: Path | None = None,
    data_root: Path | None = None,
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

    app.register_blueprint(composer.bp)
    app.register_blueprint(admin.bp)

    @app.get("/")
    def index() -> str:
        widgets = len(registry.widgets())
        errors = len(registry.errors)
        return f"Inky Dash v{VERSION} — {widgets} widget plugin(s) loaded" + (
            f", {errors} error(s)" if errors else ""
        )

    @app.get("/healthz")
    def healthz() -> dict[str, object]:
        return {
            "status": "ok",
            "version": VERSION,
            "plugins": {
                "loaded": sorted(registry.plugins.keys()),
                "errors": [{"id": e.plugin_id, "message": e.message} for e in registry.errors],
            },
        }

    return app

from __future__ import annotations

from pathlib import Path

from flask import Flask

from app import composer, plugin_loader

ROOT = Path(__file__).resolve().parent.parent
VERSION = (ROOT / "VERSION").read_text().strip()
DEFAULT_PLUGINS_DIR = ROOT / "plugins"
DEFAULT_DATA_ROOT = ROOT / "data" / "plugins"
SCHEMA_PATH = ROOT / "schema" / "plugin.schema.json"


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

    app.config["VERSION"] = VERSION
    app.config["PLUGINS_DIR"] = plugins_dir or DEFAULT_PLUGINS_DIR
    app.config["DATA_ROOT"] = data_root or DEFAULT_DATA_ROOT

    registry = plugin_loader.discover(
        app.config["PLUGINS_DIR"],
        schema_path=SCHEMA_PATH,
        data_root=app.config["DATA_ROOT"],
    )
    app.config["PLUGIN_REGISTRY"] = registry
    plugin_loader.register_routes(app, registry)
    app.register_blueprint(composer.bp)

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

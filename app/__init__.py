from __future__ import annotations

from pathlib import Path

from flask import Flask

VERSION = (Path(__file__).resolve().parent.parent / "VERSION").read_text().strip()


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index() -> str:
        return f"Inky Dash v{VERSION} — milestone 0 skeleton"

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "version": VERSION}

    return app

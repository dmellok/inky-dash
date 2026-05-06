from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, abort, jsonify, render_template, request, send_from_directory, url_for

from composer import make_blueprint as make_composer_blueprint
from config import Config
from mqtt_bridge import MqttBridge
from plugin_loader import init_plugins
from push import (
    PushBusy,
    PushManager,
    PushValidationError,
    VALID_BGS,
    VALID_SCALES,
    make_blueprint as make_push_blueprint,
)
from renderer import RenderError
from restart import schedule_restart
from scheduler import Scheduler
from state import env_file
from state.history import HistoryStore
from state.pages import DraftStore, PageStore
from state.preferences import Preferences
from state.schedules import Schedule, SchedulesStore
from state.uploads import UploadError, UploadStore

ROOT = Path(__file__).resolve().parent

# Schema for the base (non-plugin) Settings sections. Each plugin contributes
# its own section via plugin.json; the merged list is what /settings shows.
BASE_SETTINGS_SECTIONS: list[dict] = [
    {
        "title": "Server",
        "fields": [
            {"key": "HOST", "label": "Host", "type": "text", "default": "0.0.0.0",
             "help": "Interface to bind to. 0.0.0.0 = all interfaces."},
            {"key": "PORT", "label": "Port", "type": "int", "default": 5555},
            {"key": "PUBLIC_BASE_URL", "label": "Public base URL", "type": "text",
             "help": "URL the Pi listener uses to fetch rendered PNGs. Don't use 'localhost' — the Pi can't reach it."},
        ],
    },
    {
        "title": "MQTT",
        "fields": [
            {"key": "MQTT_HOST", "label": "Broker host", "type": "text", "default": "localhost"},
            {"key": "MQTT_PORT", "label": "Broker port", "type": "int", "default": 1883},
            {"key": "MQTT_USERNAME", "label": "Username", "type": "text"},
            {"key": "MQTT_PASSWORD", "label": "Password", "type": "secret"},
            {"key": "MQTT_CLIENT_ID", "label": "Client ID", "type": "text", "default": "inky-dash-companion"},
            {"key": "MQTT_TOPIC_UPDATE", "label": "Update topic", "type": "text", "default": "inky/update"},
            {"key": "MQTT_TOPIC_STATUS", "label": "Status topic", "type": "text", "default": "inky/status"},
            {"key": "MQTT_TOPIC_LOG", "label": "Log topic", "type": "text", "default": "inky/log"},
        ],
    },
    {
        "title": "Panel",
        "fields": [
            {"key": "PANEL_WIDTH", "label": "Panel width (px)", "type": "int", "default": 800},
            {"key": "PANEL_HEIGHT", "label": "Panel height (px)", "type": "int", "default": 480},
        ],
    },
    {
        "title": "Behavior",
        "fields": [
            {"key": "STATUS_STALE_SECONDS", "label": "Listener stale after (seconds)", "type": "int", "default": 120},
            {"key": "REFRESH_LOCKOUT_SECONDS", "label": "Push lockout (seconds)", "type": "int", "default": 30},
            {"key": "LOG_BUFFER_SIZE", "label": "Listener log buffer size", "type": "int", "default": 50},
            {"key": "MAX_UPLOAD_BYTES", "label": "Max upload size (bytes)", "type": "int", "default": 52428800},
        ],
    },
    {
        "title": "Storage",
        "fields": [
            {"key": "DATA_DIR", "label": "Data directory", "type": "text", "default": "data"},
            {"key": "RENDER_DIR", "label": "Render directory", "type": "text", "default": "data/renders"},
            {"key": "UPLOAD_DIR", "label": "Upload directory", "type": "text", "default": "data/uploads"},
        ],
    },
]


def _coerce_for_display(raw: str | None, type_: str, default):
    if raw is None or raw == "":
        return default
    if type_ == "int":
        try: return int(raw)
        except ValueError: return default
    if type_ == "float":
        try: return float(raw)
        except ValueError: return default
    if type_ == "bool":
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    return raw


def _validate_for_save(raw, type_: str):
    """Coerce a JSON-supplied value to the right Python type for the env file.
    Raises ValueError if the value can't be parsed into the declared type."""
    if type_ == "secret":
        return None if not raw else str(raw)
    if type_ == "bool":
        if isinstance(raw, bool): return raw
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}
    if type_ == "int":
        if raw == "" or raw is None: return None
        return int(raw)
    if type_ == "float":
        if raw == "" or raw is None: return None
        return float(raw)
    # text, color, select, image — all stored as plain strings
    return "" if raw is None else str(raw)


def _settings_section_view(*, title: str, plugin_id: str | None, fields: list[dict]) -> dict:
    """Render a settings section (base or plugin) into the API response shape.
    Secrets never leak their value back — we expose only `has_value` so the UI
    can show "(set)" / "(unset)" without revealing the secret itself."""
    out_fields: list[dict] = []
    for f in fields:
        key = f["key"]
        type_ = f.get("type", "text")
        env_value = os.environ.get(key)
        is_secret = type_ == "secret"
        out_fields.append({
            "key": key,
            "label": f.get("label", key),
            "type": type_,
            "default": f.get("default"),
            "help": f.get("help"),
            "choices": f.get("choices"),
            "choices_from": f.get("choices_from"),
            "value": None if is_secret else _coerce_for_display(env_value, type_, f.get("default")),
            "has_value": bool(env_value) if is_secret else None,
        })
    return {"title": title, "plugin_id": plugin_id, "fields": out_fields}


def create_app() -> Flask:
    config = Config.load()
    config.data_dir.mkdir(parents=True, exist_ok=True)
    config.render_dir.mkdir(parents=True, exist_ok=True)
    config.upload_dir.mkdir(parents=True, exist_ok=True)

    app = Flask(__name__)
    app.config["INKY"] = config
    app.config["MAX_CONTENT_LENGTH"] = config.max_upload_bytes

    bridge = MqttBridge(config)
    bridge.start()
    app.config["MQTT"] = bridge

    registry = init_plugins(app, config)

    page_store = PageStore(config.data_dir / "pages.json")
    draft_store = DraftStore()
    history = HistoryStore(config.data_dir / "history.db")
    uploads = UploadStore(config.upload_dir)
    schedules_store = SchedulesStore(config.data_dir / "schedules.json")
    preferences = Preferences(config.data_dir / "preferences.json")
    push_manager = PushManager(config, bridge, history, page_store, draft_store)
    scheduler = Scheduler(schedules_store, page_store, push_manager)
    scheduler.start()
    app.config["PAGES"] = page_store
    app.config["DRAFTS"] = draft_store
    app.config["HISTORY"] = history
    app.config["UPLOADS"] = uploads
    app.config["SCHEDULES"] = schedules_store
    app.config["SCHEDULER"] = scheduler
    app.config["PUSH"] = push_manager
    app.config["PREFERENCES"] = preferences
    app.register_blueprint(make_composer_blueprint(page_store, draft_store))
    app.register_blueprint(make_push_blueprint(push_manager))

    @app.context_processor
    def _inject_plugins():
        # Resolve every plugin's declared admin_nav.endpoint to a real URL
        # using `url_for`. If the endpoint isn't registered (plugin missing or
        # disabled at boot) fall back to the blueprint's root, then to '#'.
        nav_links = []
        for link in registry.nav_links():
            url = "#"
            if link.endpoint:
                try:
                    url = url_for(link.endpoint)
                except Exception:
                    url = f"/plugins/{link.plugin_id}/"
            nav_links.append({
                "label": link.label,
                "icon": link.icon,
                "endpoint": link.endpoint,
                "plugin_id": link.plugin_id,
                "url": url,
            })
        return {
            "plugin_registry": registry,
            "page_store": page_store,
            "plugin_nav_links": nav_links,
        }

    @app.get("/")
    def index():
        return render_template("index.html")

    def _editor_catalog():
        widgets = []
        for p in registry.plugins.values():
            if "widget" not in p.manifest.kinds:
                continue
            widgets.append({
                "id": p.id,
                "label": p.manifest.label,
                "icon": p.manifest.icon,
                "cell_options": p.manifest.cell_options,
                "enabled": registry.is_enabled(p.id),
            })
        # Expose weight URLs on each font so the editor can inject the global
        # font's @font-face declaration for theme tile previews.
        fonts_view = []
        for f in registry.fonts():
            fonts_view.append({
                "id": f.id,
                "label": f.id,
                "family": f.family,
                "fallback_stack": f.fallback_stack,
                "is_system": f.is_system,
                "weights": [
                    {"weight": int(w), "url": f"/plugins/{f.source_plugin}/{src}"}
                    for w, src in (f.weights or {}).items()
                ],
            })
        return {
            "widgets": widgets,
            "themes": [
                {"id": t.id, "label": t.label, "palette": t.palette}
                for t in registry.themes()
            ],
            "fonts": fonts_view,
            "default_font": preferences.get_default_font(),
        }

    @app.get("/dashboards/new")
    def dashboard_new():
        return render_template(
            "dashboards/edit.html",
            page=None,
            initial_page={
                "name": "Untitled",
                "layout": "single",
                "cells": [{"widget": ""}],
                "cell_gap": 38,
                "cell_radius": 20,
            },
            catalog=_editor_catalog(),
            panel_width=config.panel_width,
            panel_height=config.panel_height,
        )

    @app.get("/dashboards/<page_id>/edit")
    def dashboard_edit(page_id):
        page = page_store.get(page_id)
        if not page:
            abort(404)
        return render_template(
            "dashboards/edit.html",
            page=page,
            initial_page=page.to_json(),
            catalog=_editor_catalog(),
            panel_width=config.panel_width,
            panel_height=config.panel_height,
        )

    @app.get("/renders/<path:filename>")
    def renders(filename: str):
        return send_from_directory(config.render_dir, filename)

    # ---------- uploads ----------------------------------------------------

    @app.post("/api/uploads")
    def api_upload():
        try:
            entry = uploads.save(
                request.files.get("file"),
                max_bytes=config.max_upload_bytes,
            )
        except UploadError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(entry), 201

    @app.post("/api/uploads/from-url")
    def api_upload_from_url():
        body = request.get_json(silent=True) or {}
        url = (body.get("url") or "").strip()
        if not (url.startswith("http://") or url.startswith("https://")):
            return jsonify({"error": "url must start with http:// or https://"}), 400
        from urllib.request import Request, urlopen
        from urllib.parse import urlparse
        try:
            req = Request(url, headers={"User-Agent": "Inky Dash"})
            with urlopen(req, timeout=20) as resp:
                ct = (resp.headers.get_content_type() or "").lower()
                # Cap read at max_upload_bytes to avoid loading multi-GB downloads.
                data = resp.read(config.max_upload_bytes + 1)
        except Exception as exc:
            return jsonify({"error": f"fetch failed: {exc}"}), 502
        if len(data) > config.max_upload_bytes:
            return jsonify({"error": f"fetch exceeds {config.max_upload_bytes} bytes"}), 413

        # Pick extension from Content-Type, falling back to URL path suffix.
        ct_to_ext = {
            "image/png": ".png", "image/jpeg": ".jpg", "image/jpg": ".jpg",
            "image/gif": ".gif", "image/webp": ".webp",
        }
        ext = ct_to_ext.get(ct)
        if not ext:
            path_ext = Path(urlparse(url).path).suffix.lower()
            if path_ext in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
                ext = ".jpeg" if path_ext == ".jpeg" else path_ext
        if not ext:
            return jsonify({"error": f"unsupported content-type {ct!r}"}), 415

        try:
            entry = uploads.save_bytes(
                data,
                ext=ext,
                original_name=Path(urlparse(url).path).name or "url-upload",
                max_bytes=config.max_upload_bytes,
            )
        except UploadError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(entry), 201

    @app.get("/uploads/<path:filename>")
    def serve_upload(filename: str):
        if uploads.path(filename) is None:
            abort(404)
        return send_from_directory(uploads.dir, filename)

    @app.get("/api/uploads")
    def list_uploads():
        return jsonify({"uploads": uploads.list_recent(limit=50)})

    # ---------- image compose + push --------------------------------------

    _SCALE_TO_OBJECT_FIT = {
        "fit": "contain",
        "fill": "cover",
        "stretch": "fill",
        "center": "none",
    }

    @app.get("/compose/image/<path:image_id>")
    def compose_image(image_id):
        if uploads.path(image_id) is None:
            abort(404)
        scale = request.args.get("scale", "fit")
        bg = request.args.get("bg", "white")
        if scale not in VALID_SCALES:
            return jsonify({"error": f"invalid scale {scale!r}"}), 400
        if bg not in VALID_BGS:
            return jsonify({"error": f"invalid bg {bg!r}"}), 400
        return render_template(
            "compose_image.html",
            view={
                "image_id": image_id,
                "image_url": f"/uploads/{image_id}",
                "panel": [config.panel_width, config.panel_height],
                "scale": scale,
                "bg": bg,
            },
            object_fit=_SCALE_TO_OBJECT_FIT[scale],
        )

    @app.post("/api/push-webpage")
    def api_push_webpage():
        body = request.get_json(silent=True) or {}
        url = (body.get("url") or "").strip()
        try:
            extra_wait_ms = int(body.get("extra_wait_ms") or 0)
        except (TypeError, ValueError):
            return jsonify({"error": "extra_wait_ms must be an integer"}), 400
        if extra_wait_ms < 0 or extra_wait_ms > 60000:
            return jsonify({"error": "extra_wait_ms must be in [0, 60000]"}), 400
        try:
            return jsonify(push_manager.push_webpage(
                url=url,
                extra_wait_ms=extra_wait_ms,
                options={k: body[k] for k in ("rotate", "scale", "bg", "saturation") if k in body},
            ))
        except PushBusy as exc:
            return jsonify({"error": str(exc)}), 409
        except PushValidationError as exc:
            return jsonify({"error": str(exc)}), 400
        except RenderError as exc:
            return jsonify({"error": f"render failed: {exc}"}), 500
        except Exception as exc:
            return jsonify({"error": f"{type(exc).__name__}: {exc}"}), 500

    @app.post("/api/push-image/<path:image_id>")
    def api_push_image(image_id):
        if uploads.path(image_id) is None:
            abort(404)
        opts = request.get_json(silent=True) or {}
        scale = opts.get("scale", "fit")
        bg = opts.get("bg", "white")
        # Compose URL bakes scale + bg (incl. blurred) into the rendered PNG
        # via CSS object-fit and filter:blur. Wire payload's scale/bg are
        # forced to "fit"/"white" since the PNG already fills the panel.
        from urllib.parse import urlencode
        query = urlencode({"scale": scale, "bg": bg, "for_push": "1"})
        compose_url = f"http://127.0.0.1:{config.port}/compose/image/{image_id}?{query}"
        try:
            return jsonify(push_manager.push(
                source="image",
                target={"source_image": image_id},
                options=opts,
                compose_url=compose_url,
                wire_overrides={"scale": "fit", "bg": "white"},
            ))
        except PushBusy as exc:
            return jsonify({"error": str(exc)}), 409
        except PushValidationError as exc:
            return jsonify({"error": str(exc)}), 400
        except RenderError as exc:
            return jsonify({"error": f"render failed: {exc}"}), 500
        except Exception as exc:
            return jsonify({"error": f"{type(exc).__name__}: {exc}"}), 500

    @app.get("/send")
    def send_page():
        return render_template(
            "send.html",
            panel_width=config.panel_width,
            panel_height=config.panel_height,
        )

    # ---------- schedules --------------------------------------------------

    @app.get("/schedules")
    def schedules_page():
        return render_template("schedules/list.html")

    @app.get("/schedules/new")
    def schedule_new():
        return render_template(
            "schedules/edit.html",
            schedule=None,
            initial=None,
            pages=[p.to_json() for p in page_store.list()],
        )

    @app.get("/schedules/<sid>/edit")
    def schedule_edit(sid):
        s = schedules_store.get(sid)
        if not s:
            abort(404)
        return render_template(
            "schedules/edit.html",
            schedule=s,
            initial=s.to_json(),
            pages=[p.to_json() for p in page_store.list()],
        )

    @app.get("/api/schedules")
    def api_list_schedules():
        return jsonify({"schedules": [s.to_json() for s in schedules_store.list()]})

    @app.get("/api/schedules/<sid>")
    def api_get_schedule(sid):
        s = schedules_store.get(sid)
        if not s:
            abort(404)
        return jsonify(s.to_json())

    @app.post("/api/schedules")
    def api_create_schedule():
        try:
            data = request.get_json(force=True) or {}
            if not data.get("id"):
                data["id"] = schedules_store.unique_slug(data.get("name", "schedule"))
            s = Schedule.from_json(data)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400
        schedules_store.upsert(s)
        return jsonify(s.to_json()), 201

    @app.put("/api/schedules/<sid>")
    def api_update_schedule(sid):
        try:
            data = request.get_json(force=True) or {}
            data["id"] = sid
            s = Schedule.from_json(data)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400
        schedules_store.upsert(s)
        return jsonify(s.to_json())

    @app.delete("/api/schedules/<sid>")
    def api_delete_schedule(sid):
        if not schedules_store.delete(sid):
            abort(404)
        return ("", 204)

    @app.post("/api/schedules/reorder")
    def api_reorder_schedules():
        body = request.get_json(force=True) or {}
        ids = body.get("ids")
        if not isinstance(ids, list):
            return jsonify({"error": "ids must be a list of schedule ids"}), 400
        schedules_store.reorder([str(x) for x in ids])
        return jsonify({"ok": True})

    # ---------- widget manager ---------------------------------------------

    @app.get("/widgets")
    def widgets_page():
        return render_template("widgets/list.html")

    @app.get("/api/widgets")
    def api_widgets_list():
        out = []
        for p in registry.plugins.values():
            out.append({
                "id": p.id,
                "label": p.manifest.label,
                "icon": p.manifest.icon,
                "version": p.manifest.version,
                "kinds": p.manifest.kinds,
                "enabled": registry.is_enabled(p.id),
                "error": p.error,
                "has_client_js": p.has_client_js,
                "has_client_css": p.has_client_css,
                "has_blueprint": (
                    p.module is not None
                    and callable(getattr(p.module, "blueprint", None))
                ),
                "settings_keys": (
                    [f.key for f in p.manifest.settings.fields]
                    if p.manifest.settings else []
                ),
                "synthetic": p.module is None and p.error is None and p.id == "user_themes",
            })
        return jsonify({"plugins": out})

    @app.put("/api/widgets/<plugin_id>")
    def api_widgets_set_enabled(plugin_id):
        body = request.get_json(silent=True) or {}
        if "enabled" not in body:
            return jsonify({"error": "body must include 'enabled'"}), 400
        ok = registry.set_enabled(plugin_id, bool(body["enabled"]))
        if not ok:
            abort(404)
        return jsonify({
            "id": plugin_id,
            "enabled": registry.is_enabled(plugin_id),
        })

    # ---------- settings (merged base + plugin sections) -------------------

    @app.get("/settings")
    def settings_page():
        return render_template("settings.html")

    @app.get("/api/settings")
    def api_settings_get():
        sections: list[dict] = []
        for s in BASE_SETTINGS_SECTIONS:
            sections.append(_settings_section_view(
                title=s["title"], plugin_id=None, fields=s["fields"]))
        for s in registry.settings_sections():
            sections.append(_settings_section_view(
                title=s.title,
                plugin_id=s.plugin_id,
                fields=[
                    {
                        "key": f.key, "label": f.label, "type": f.type,
                        "default": f.default,
                        "choices": f.choices,
                        "choices_from": f.choices_from,
                    } for f in s.fields
                ],
            ))
        env_path = ROOT / ".env"
        return jsonify({"sections": sections, "env_path": str(env_path)})

    @app.post("/api/settings")
    def api_settings_save():
        body = request.get_json(force=True) or {}
        values = body.get("values") or {}

        # Merge known fields from base + plugins so we know each one's type.
        known_types: dict[str, str] = {}
        for s in BASE_SETTINGS_SECTIONS:
            for f in s["fields"]:
                known_types[f["key"]] = f.get("type", "text")
        for s in registry.settings_sections():
            for f in s.fields:
                known_types[f.key] = f.type

        updates: dict = {}
        for key, raw in values.items():
            if key not in known_types:
                continue  # silently drop unknown keys
            try:
                coerced = _validate_for_save(raw, known_types[key])
            except (TypeError, ValueError) as exc:
                return jsonify({"error": f"{key}: {exc}"}), 400
            # secret with empty value = "keep current", so skip writing.
            if known_types[key] == "secret" and coerced is None:
                continue
            updates[key] = coerced

        env_path = ROOT / ".env"
        try:
            written_keys = env_file.update_env(env_path, updates)
        except OSError as exc:
            return jsonify({"error": f"could not write {env_path}: {exc}"}), 500

        skip_restart = body.get("_no_restart") or request.args.get("_no_restart") == "1"
        if not skip_restart:
            schedule_restart(config.host, config.port, delay=0.5)

        return jsonify({
            "saved": True,
            "updated_keys": written_keys,
            "env_path": str(env_path),
            "restart_in_seconds": 0 if skip_restart else 0.5,
        })

    @app.get("/api/status")
    def api_status():
        return jsonify(bridge.snapshot())

    @app.get("/api/choices/<name>")
    def api_choices(name):
        return jsonify({"choices": registry.choices(name)})

    @app.get("/api/plugins")
    def api_plugins():
        return jsonify({
            "plugins": [
                {
                    "id": p.id,
                    "label": p.manifest.label,
                    "icon": p.manifest.icon,
                    "version": p.manifest.version,
                    "kinds": p.manifest.kinds,
                    "enabled": registry.is_enabled(p.id),
                    "error": p.error,
                    "has_client_js": p.has_client_js,
                    "has_client_css": p.has_client_css,
                    "cell_options": p.manifest.cell_options,
                    "choice_providers": p.manifest.choice_providers,
                    "admin_nav": (
                        {
                            "label": p.manifest.admin_nav.label,
                            "icon": p.manifest.admin_nav.icon,
                            "endpoint": p.manifest.admin_nav.endpoint,
                        }
                        if p.manifest.admin_nav else None
                    ),
                    "settings": (
                        {
                            "title": p.manifest.settings.title,
                            "fields": [
                                {
                                    "key": f.key, "label": f.label, "type": f.type,
                                    "default": f.default,
                                    "choices": f.choices,
                                    "choices_from": f.choices_from,
                                }
                                for f in p.manifest.settings.fields
                            ],
                        }
                        if p.manifest.settings else None
                    ),
                }
                for p in registry.plugins.values()
            ],
            "themes": [
                {"id": t.id, "label": t.label, "source": t.source_plugin}
                for t in registry.themes()
            ],
            "fonts": [
                {
                    "id": f.id, "family": f.family,
                    "source": f.source_plugin,
                    "weights": list(f.weights.keys()),
                    "is_system": f.is_system,
                }
                for f in registry.fonts()
            ],
            "nav_links": [
                {
                    "label": n.label, "icon": n.icon,
                    "endpoint": n.endpoint, "plugin_id": n.plugin_id,
                }
                for n in registry.nav_links()
            ],
            "settings_sections": [
                {
                    "plugin_id": s.plugin_id, "title": s.title,
                    "fields": [f.__dict__ for f in s.fields],
                }
                for s in registry.settings_sections()
            ],
        })

    return app


app = create_app()


if __name__ == "__main__":
    cfg: Config = app.config["INKY"]
    app.run(host=cfg.host, port=cfg.port, threaded=True, use_reloader=False)

"""Theme builder admin plugin.

Lists every loaded theme (bundled + user) and lets the user create / clone /
edit / delete themes that live as JSON files under `data/themes/`. The
loader's synthetic `user_themes` plugin already picks those up at boot;
this plugin adds the editor UI plus a `reload_user_themes()` call after
each save so changes take effect hot.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from flask import Blueprint, abort, current_app, jsonify, render_template, request

PALETTE_KEYS = (
    "bg", "surface", "surface-2",
    "fg", "fg-soft", "muted",
    "accent", "accent-soft",
    "divider", "danger", "warn", "ok",
)

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text.strip().lower()).strip("-") or "theme"


def _themes_dir() -> Path:
    return current_app.config["INKY"].data_dir / "themes"


def _registry():
    return current_app.config["PLUGINS"]


def _validate_palette(palette: dict) -> dict[str, str]:
    if not isinstance(palette, dict):
        raise ValueError("palette must be an object")
    out: dict[str, str] = {}
    for key in PALETTE_KEYS:
        v = palette.get(key)
        if not isinstance(v, str):
            raise ValueError(f"missing or non-string palette key: {key}")
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", v.strip()):
            raise ValueError(f"palette.{key} must be a #RRGGBB hex, got {v!r}")
        out[key] = v.strip().lower()
    return out


def blueprint():
    bp = Blueprint("theme_builder", __name__, template_folder="templates")

    @bp.route("/")
    def index():
        # Namespaced template path so plugin templates don't collide in
        # Flask's process-global template loader.
        return render_template("theme_builder/builder.html")

    @bp.get("/api/themes")
    def api_list():
        registry = _registry()
        bundled_ids: set[str] = set()
        user_ids: set[str] = set()
        for plugin in registry.plugins.values():
            if plugin.id == "user_themes":
                user_ids = {t.id for t in plugin.manifest.themes}
            elif "theme" in plugin.kinds:
                for t in plugin.manifest.themes:
                    bundled_ids.add(t.id)
        out = []
        for t in registry.themes():
            out.append({
                "id": t.id,
                "label": t.label,
                "palette": dict(t.palette),
                "font": t.font,
                "source_plugin": t.source_plugin,
                "is_user": t.id in user_ids and t.id not in bundled_ids,
                "is_bundled": t.id in bundled_ids,
            })
        fonts = []
        for f in registry.fonts():
            fonts.append({
                "id": f.id,
                "label": f.family,
                "is_system": f.is_system,
                "weights": [
                    {"weight": int(w), "url": f"/plugins/{f.source_plugin}/{src}"}
                    for w, src in (f.weights or {}).items()
                ],
            })
        return jsonify({
            "themes": out,
            "palette_keys": list(PALETTE_KEYS),
            "fonts": fonts,
        })

    @bp.post("/api/themes")
    def api_save():
        body = request.get_json(force=True) or {}
        try:
            palette = _validate_palette(body.get("palette") or {})
            label = str(body.get("label") or "").strip()
            if not label:
                raise ValueError("label is required")
            theme_id = str(body.get("id") or "").strip() or _slug(label)
            theme_id = _slug(theme_id)
        except (TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400

        # Refuse to overwrite a bundled theme — the user must clone first.
        registry = _registry()
        for plugin in registry.plugins.values():
            if plugin.id == "user_themes":
                continue
            if "theme" not in plugin.kinds:
                continue
            for t in plugin.manifest.themes:
                if t.id == theme_id:
                    return jsonify({
                        "error": f"'{theme_id}' is a bundled theme — clone it first",
                    }), 409

        font_raw = body.get("font")
        font_id: str | None = None
        if isinstance(font_raw, str) and font_raw.strip():
            candidate = font_raw.strip()
            if registry.font(candidate) is None:
                return jsonify({"error": f"unknown font {candidate!r}"}), 400
            font_id = candidate

        themes_dir = _themes_dir()
        themes_dir.mkdir(parents=True, exist_ok=True)
        path = themes_dir / f"{theme_id}.json"
        body_out: dict = {"id": theme_id, "label": label, "palette": palette}
        # Per rule 7: omit empty optional fields.
        if font_id:
            body_out["font"] = font_id
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(body_out, indent=2), encoding="utf-8")
        tmp.replace(path)

        registry.reload_user_themes(themes_dir)
        return jsonify({"ok": True, **body_out}), 201

    @bp.delete("/api/themes/<theme_id>")
    def api_delete(theme_id):
        themes_dir = _themes_dir()
        path = themes_dir / f"{theme_id}.json"
        if not path.exists():
            abort(404)
        path.unlink()
        _registry().reload_user_themes(themes_dir)
        return ("", 204)

    @bp.get("/api/font-default")
    def api_get_default_font():
        prefs = current_app.config.get("PREFERENCES")
        return jsonify({"font": prefs.get_default_font() if prefs else None})

    @bp.put("/api/font-default")
    def api_set_default_font():
        body = request.get_json(force=True) or {}
        raw = body.get("font")
        font_id: str | None = None
        if isinstance(raw, str) and raw.strip():
            candidate = raw.strip()
            if _registry().font(candidate) is None:
                return jsonify({"error": f"unknown font {candidate!r}"}), 400
            font_id = candidate
        prefs = current_app.config.get("PREFERENCES")
        if prefs is None:
            return jsonify({"error": "preferences store unavailable"}), 500
        prefs.set_default_font(font_id)
        return jsonify({"font": font_id})

    @bp.get("/api/font-weight")
    def api_get_font_weight():
        prefs = current_app.config.get("PREFERENCES")
        return jsonify({"weight": prefs.get_font_weight() if prefs else 400})

    @bp.put("/api/font-weight")
    def api_set_font_weight():
        body = request.get_json(force=True) or {}
        raw = body.get("weight")
        try:
            weight = int(raw) if raw is not None else 400
        except (TypeError, ValueError):
            return jsonify({"error": "weight must be an integer"}), 400
        if weight < 100 or weight > 900 or weight % 100 != 0:
            return jsonify({"error": "weight must be a 100-step value in 100..900"}), 400
        prefs = current_app.config.get("PREFERENCES")
        if prefs is None:
            return jsonify({"error": "preferences store unavailable"}), 500
        prefs.set_font_weight(weight)
        return jsonify({"weight": weight})

    return bp

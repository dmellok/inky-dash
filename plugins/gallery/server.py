"""Gallery widget — picks an image from a local folder (random or sequential).

Galleries are managed via the admin page at `/plugins/gallery/` and persisted
to `data/galleries.json`. Sequential galleries advance a per-gallery cursor at
push time; previewing reads-without-advancing so the editor iframe doesn't
mutate state on every keystroke.

Watch out: paths starting with '/' must NOT have the leading slash trimmed
(a v2 bug we don't repeat).
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import threading
import uuid
from pathlib import Path
from typing import Any

from flask import Blueprint, abort, current_app, jsonify, render_template, request

ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
_lock = threading.Lock()


# ---------- storage ----------------------------------------------------


def _store_path() -> Path:
    return current_app.config["INKY"].data_dir / "galleries.json"


def _load() -> dict[str, dict]:
    p = _store_path()
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save(galleries: dict[str, dict]) -> None:
    p = _store_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(galleries, indent=2), encoding="utf-8")
    tmp.replace(p)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _validate_folder(folder: str, *, allow_outside: bool) -> Path | None:
    """Return the resolved Path if it's a real directory; None otherwise.
    NOTE: do NOT strip a leading '/' — absolute paths are fine if allowed."""
    if not folder:
        return None
    p = Path(folder).expanduser()
    try:
        resolved = p.resolve()
    except OSError:
        return None
    if not resolved.is_dir():
        return None
    if not allow_outside:
        try:
            resolved.relative_to(_project_root())
        except ValueError:
            return None
    return resolved


def _list_images(folder: Path) -> list[Path]:
    return sorted(
        (p for p in folder.iterdir()
         if p.is_file() and p.suffix.lower() in ALLOWED_EXTS),
        key=lambda p: p.name.lower(),
    )


def _pick(gallery: dict, mode: str, allow_outside: bool, *, advance: bool) -> Path | None:
    """Pick an image. `mode` is supplied by the caller (per-cell option from
    the dashboard editor) — galleries no longer carry their own mode."""
    folder = _validate_folder(gallery.get("folder", ""), allow_outside=allow_outside)
    if not folder:
        return None
    images = _list_images(folder)
    if not images:
        return None
    if mode == "sequential":
        cursor = int(gallery.get("cursor") or 0) % len(images)
        chosen = images[cursor]
        if advance:
            gallery["cursor"] = (cursor + 1) % len(images)
        return chosen
    import random
    return random.choice(images)


def _embed(image_path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(image_path))
    if not mime or not mime.startswith("image/"):
        mime = "image/jpeg"
    data = image_path.read_bytes()
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


# ---------- choice provider --------------------------------------------


def choices(name: str):
    if name != "galleries":
        return []
    with _lock:
        galleries = _load()
    return [
        {"value": gid, "label": g.get("name") or gid}
        for gid, g in galleries.items()
    ]


# ---------- widget fetch -----------------------------------------------


def fetch(options, settings, *, panel_w, panel_h, preview=False):
    gid = options.get("gallery") or ""
    allow_outside = bool(settings.get("GALLERY_ALLOW_OUTSIDE_SANDBOX", True))
    if not gid:
        return {"error": "no gallery selected"}
    with _lock:
        galleries = _load()
        gallery = galleries.get(gid)
        if not gallery:
            return {"error": f"gallery '{gid}' not found"}
        # Mode is now strictly a per-cell option set in the dashboard editor.
        # Default to random if the cell didn't pick one.
        mode = options.get("mode") if options.get("mode") in ("random", "sequential") else "random"
        scratch = dict(gallery)
        chosen = _pick(scratch, mode, allow_outside, advance=not preview)
        if not preview and mode == "sequential" and chosen is not None:
            galleries[gid]["cursor"] = scratch.get("cursor", 0)
            _save(galleries)
    if chosen is None:
        return {"error": f"no images in {gallery.get('folder')!r}"}
    try:
        return {
            "img": _embed(chosen),
            "name": chosen.name,
            "gallery_name": gallery.get("name", gid),
        }
    except OSError as exc:
        return {"error": f"read failed: {exc}"}


# ---------- admin blueprint --------------------------------------------


def blueprint():
    bp = Blueprint("gallery", __name__, template_folder="templates")

    @bp.route("/")
    def index():
        # Namespaced template path. Flask's template loader is process-global
        # so two plugins both named admin.html would otherwise collide.
        return render_template("gallery/admin.html")

    @bp.get("/api/galleries")
    def api_list():
        with _lock:
            galleries = _load()
        # Augment with image count + path validity
        allow_outside = bool(os.environ.get("GALLERY_ALLOW_OUTSIDE_SANDBOX", "true").lower() in {"1","true","yes","on"})
        out = []
        for gid, g in galleries.items():
            folder = _validate_folder(g.get("folder", ""), allow_outside=allow_outside)
            count = len(_list_images(folder)) if folder else 0
            out.append({
                "id": gid,
                "name": g.get("name", gid),
                "folder": g.get("folder", ""),
                "cursor": int(g.get("cursor") or 0),
                "image_count": count,
                "valid": folder is not None,
            })
        return jsonify({"galleries": out})

    @bp.post("/api/galleries")
    def api_create():
        body = request.get_json(silent=True) or {}
        name = (body.get("name") or "").strip()
        folder = (body.get("folder") or "").strip()
        if not name or not folder:
            return jsonify({"error": "name and folder are required"}), 400
        with _lock:
            galleries = _load()
            gid = body.get("id") or uuid.uuid4().hex[:10]
            galleries[gid] = {
                "name": name,
                "folder": folder,
                "cursor": 0,
            }
            _save(galleries)
        return jsonify({"id": gid, **galleries[gid]}), 201

    @bp.put("/api/galleries/<gid>")
    def api_update(gid):
        body = request.get_json(silent=True) or {}
        with _lock:
            galleries = _load()
            if gid not in galleries:
                abort(404)
            for key in ("name", "folder"):
                if key in body:
                    galleries[gid][key] = body[key]
            if "cursor" in body:
                galleries[gid]["cursor"] = int(body["cursor"]) or 0
            # Drop any legacy `mode` field still hanging around in storage.
            galleries[gid].pop("mode", None)
            _save(galleries)
        return jsonify({"id": gid, **galleries[gid]})

    @bp.delete("/api/galleries/<gid>")
    def api_delete(gid):
        with _lock:
            galleries = _load()
            if gid not in galleries:
                abort(404)
            del galleries[gid]
            _save(galleries)
        return ("", 204)

    return bp

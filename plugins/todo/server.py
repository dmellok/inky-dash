"""Todo widget + admin plugin.

State lives in `data/todos.json` (a flat list of items). The admin page at
`/plugins/todo/` is a quick-entry form plus per-row done/strike/delete.
Completed items vanish after `TODO_PRUNE_HOURS` (default 24) — pruning
happens at fetch time but ONLY when not in preview mode, matching the
gallery convention.
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from flask import Blueprint, abort, current_app, jsonify, render_template, request

_lock = threading.Lock()


# ---------- storage ----------------------------------------------------


def _path() -> Path:
    return current_app.config["INKY"].data_dir / "todos.json"


def _load() -> list[dict]:
    p = _path()
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save(items: list[dict]) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(items, indent=2), encoding="utf-8")
    tmp.replace(p)


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _prune(items: list[dict], hours: int) -> tuple[list[dict], int]:
    if hours <= 0:
        return items, 0
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=hours)
    keep, dropped = [], 0
    for item in items:
        ca = item.get("completed_at")
        if item.get("completed") and ca:
            try:
                # Tolerate both 'Z' and '+00:00' suffixes.
                completed_at = datetime.fromisoformat(ca.replace("Z", "+00:00"))
                if completed_at < cutoff:
                    dropped += 1
                    continue
            except Exception:
                pass
        keep.append(item)
    return keep, dropped


# ---------- widget fetch -----------------------------------------------


def fetch(options, settings, *, panel_w, panel_h, preview=False):
    style = options.get("style") or "stacked"
    show_completed = bool(options.get("show_completed", True))
    prune_hours = int(settings.get("TODO_PRUNE_HOURS") or 24)

    with _lock:
        items = _load()
        if not preview:
            kept, dropped = _prune(items, prune_hours)
            if dropped:
                _save(kept)
            items = kept

    visible = [it for it in items if show_completed or not it.get("completed")]
    return {"items": visible, "style": style, "now": _now_iso()}


# ---------- admin blueprint --------------------------------------------


def blueprint():
    bp = Blueprint("todo", __name__, template_folder="templates")

    @bp.route("/")
    def index():
        # Namespaced template path. Flask's template loader is process-global
        # so two plugins both named admin.html would otherwise collide.
        return render_template("todo/admin.html")

    @bp.get("/api/items")
    def list_items():
        with _lock:
            items = _load()
        return jsonify({"items": items})

    @bp.post("/api/items")
    def add_item():
        body = request.get_json(silent=True) or {}
        text = (body.get("text") or "").strip()
        if not text:
            return jsonify({"error": "text is required"}), 400
        item = {
            "id": uuid.uuid4().hex[:12],
            "text": text,
            "completed": False,
            "created_at": _now_iso(),
            "completed_at": None,
        }
        with _lock:
            items = _load()
            items.append(item)
            _save(items)
        return jsonify(item), 201

    @bp.put("/api/items/<item_id>")
    def update_item(item_id):
        body = request.get_json(silent=True) or {}
        with _lock:
            items = _load()
            for it in items:
                if it["id"] == item_id:
                    if "text" in body:
                        text = (body["text"] or "").strip()
                        if not text:
                            return jsonify({"error": "text cannot be empty"}), 400
                        it["text"] = text
                    if "completed" in body:
                        it["completed"] = bool(body["completed"])
                        it["completed_at"] = _now_iso() if it["completed"] else None
                    _save(items)
                    return jsonify(it)
        abort(404)

    @bp.delete("/api/items/<item_id>")
    def delete_item(item_id):
        with _lock:
            items = _load()
            new_items = [it for it in items if it["id"] != item_id]
            if len(new_items) == len(items):
                abort(404)
            _save(new_items)
        return ("", 204)

    @bp.post("/api/prune")
    def prune_now():
        # Manual button = "drop all completed items, now". The age-based
        # window in TODO_PRUNE_HOURS is only consulted by the widget's
        # auto-prune at fetch time; a user clicking "Prune now" expects
        # immediate cleanup regardless of how recently they ticked things.
        with _lock:
            items = _load()
            kept = [it for it in items if not it.get("completed")]
            dropped = len(items) - len(kept)
            if dropped:
                _save(kept)
        return jsonify({"pruned": dropped, "remaining": len(kept)})

    return bp

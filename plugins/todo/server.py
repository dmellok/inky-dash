"""Todo state + admin blueprint.

State lives at ``data/plugins/todo/items.json`` (the loader's data_dir).
Items are JSON: ``{id, text, created_at, completed_at?}``.

Marking an item done sets ``completed_at`` rather than deleting; completed
items linger for 24h so the dashboard reflects recent progress, then prune
themselves automatically on the next read.
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from flask import Blueprint, current_app, redirect, render_template_string, request

_ITEMS_FILE = "items.json"
_COMPLETED_TTL = 24 * 60 * 60  # 24 hours


def _store_path() -> Path:
    plugin = current_app.config["PLUGIN_REGISTRY"].plugins["todo"]
    return plugin.data_dir / _ITEMS_FILE


def _load(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(items, indent=2))
    tmp.replace(path)


def _prune_expired(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop items whose completed_at is older than _COMPLETED_TTL."""
    now = time.time()
    return [
        item
        for item in items
        if not item.get("completed_at")
        or now - float(item["completed_at"]) < _COMPLETED_TTL
    ]


def _sorted(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Open items first (newest-first by created_at); completed last
    (most-recently-completed first), so the dashboard shows the freshest
    achievements on top of the done pile."""
    open_items = sorted(
        (i for i in items if not i.get("completed_at")),
        key=lambda i: i.get("created_at", 0),
        reverse=True,
    )
    done_items = sorted(
        (i for i in items if i.get("completed_at")),
        key=lambda i: i.get("completed_at", 0),
        reverse=True,
    )
    return [*open_items, *done_items]


def _read_and_prune(path: Path) -> list[dict[str, Any]]:
    """Load, drop anything past TTL, persist if pruning happened."""
    items = _load(path)
    pruned = _prune_expired(items)
    if len(pruned) != len(items):
        _save(path, pruned)
    return pruned


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    path = Path(ctx["data_dir"]) / _ITEMS_FILE
    items = _sorted(_read_and_prune(path))
    return {"items": items}


_TEMPLATE = """
<!doctype html>
<html lang="en"><head>
  <meta charset="utf-8">
  <title>Todo — Inky Dash</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="/static/icons/phosphor.css">
  <link rel="stylesheet" href="/static/style/tokens.css">
  <script>
    (function () {
      try {
        var theme = localStorage.getItem('inky_theme') || 'auto';
        var accent = localStorage.getItem('inky_accent');
        var root = document.documentElement;
        var isDark =
          theme === 'dark' ||
          (theme === 'auto' &&
            window.matchMedia &&
            window.matchMedia('(prefers-color-scheme: dark)').matches);
        if (isDark) root.dataset.theme = 'dark';
        else root.removeAttribute('data-theme');
        if (accent) root.style.setProperty('--id-accent', accent);
      } catch (_) {}
    })();
  </script>
  <script type="module" src="/static/dist/_components.js"></script>
  <style>
    body {
      font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    }
    .container { max-width: 540px; margin: 0 auto; padding: 24px 16px 48px; }
    h1 { font-size: 22px; margin: 0 0 16px; }
    form.add { display: flex; gap: 8px; margin-bottom: 24px; }
    form.add input[type=text] {
      flex: 1; padding: 10px 12px; border: 2px solid var(--id-divider);
      border-radius: 6px; font: inherit; min-height: 44px; box-sizing: border-box;
      background: var(--id-surface); color: var(--id-fg);
    }
    form.add button {
      padding: 0 16px; min-height: 44px; border: 0; border-radius: 6px;
      background: var(--id-accent); color: white; font: inherit;
      font-weight: 600; cursor: pointer; display: inline-flex;
      align-items: center; gap: 6px;
    }
    form.add button:hover { background: var(--id-accent-soft); }
    .section-title {
      font-size: 13px; font-weight: 600; text-transform: uppercase;
      letter-spacing: 0.05em; color: var(--id-fg-soft);
      margin: 24px 0 8px;
    }
    ul.items {
      list-style: none; padding: 0; margin: 0;
      background: var(--id-surface);
      border: 2px solid var(--id-divider); border-radius: 8px; overflow: hidden;
    }
    ul.items li {
      display: flex; align-items: center; gap: 12px;
      padding: 12px 14px; border-bottom: 2px solid var(--id-divider);
    }
    ul.items li:last-child { border-bottom: 0; }
    ul.items li form { display: contents; }
    ul.items li button {
      padding: 6px 12px; border: 2px solid var(--id-divider);
      border-radius: 6px; background: var(--id-surface); color: var(--id-fg);
      font: inherit; font-size: 13px; cursor: pointer;
      display: inline-flex; align-items: center; gap: 4px;
    }
    ul.items li button:hover { background: var(--id-surface2); }
    ul.items li.done { color: var(--id-fg-soft); }
    ul.items li.done .text { text-decoration: line-through; }
    .text { flex: 1; }
    .meta { font-size: 12px; color: var(--id-fg-soft); white-space: nowrap; }
    .empty {
      color: var(--id-fg-soft); font-style: italic; padding: 32px 16px;
      text-align: center; background: var(--id-surface);
      border: 2px dashed var(--id-divider); border-radius: 8px;
    }
    .hint {
      font-size: 12px; color: var(--id-fg-soft);
      margin-top: 16px; text-align: center;
    }
  </style>
</head><body>
  <id-nav></id-nav>
  <div class="container">
    <h1><i class="ph ph-list-checks" style="color: var(--id-accent);"></i> Todo</h1>
    <form class="add" method="post" action="/plugins/todo/add">
      <input type="text" name="text" placeholder="What needs doing?" autofocus required maxlength="200">
      <button type="submit"><i class="ph ph-plus"></i> Add</button>
    </form>
    {% if open_items %}
    <ul class="items">
      {% for item in open_items %}
      <li>
        <span class="text">{{ item.text }}</span>
        <form method="post" action="/plugins/todo/done/{{ item.id }}">
          <button type="submit"><i class="ph ph-check"></i> Done</button>
        </form>
      </li>
      {% endfor %}
    </ul>
    {% else %}
    <p class="empty">All done. Add an item above.</p>
    {% endif %}

    {% if done_items %}
    <p class="section-title">Recently done · auto-prunes after 24h</p>
    <ul class="items">
      {% for item in done_items %}
      <li class="done">
        <i class="ph ph-check-circle-fill" style="color: var(--id-ok, #16a34a);"></i>
        <span class="text">{{ item.text }}</span>
        <span class="meta">{{ item.completed_age }}</span>
        <form method="post" action="/plugins/todo/undone/{{ item.id }}">
          <button type="submit"><i class="ph ph-arrow-counter-clockwise"></i> Undo</button>
        </form>
        <form method="post" action="/plugins/todo/delete/{{ item.id }}">
          <button type="submit" title="Delete now"><i class="ph ph-trash"></i></button>
        </form>
      </li>
      {% endfor %}
    </ul>
    {% endif %}

    <p class="hint">Completed items linger for 24 hours, then prune themselves.</p>
  </div>
</body></html>
"""


def _human_age(seconds: float) -> str:
    seconds = max(0, int(seconds))
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    return f"{hours // 24}d ago"


def blueprint() -> Blueprint:
    bp = Blueprint("todo_admin", __name__)

    @bp.get("/")
    def index() -> str:
        items = _read_and_prune(_store_path())
        now = time.time()
        open_items = [i for i in items if not i.get("completed_at")]
        open_items.sort(key=lambda i: i.get("created_at", 0), reverse=True)
        done_items = [i for i in items if i.get("completed_at")]
        done_items.sort(key=lambda i: i.get("completed_at", 0), reverse=True)
        for i in done_items:
            i["completed_age"] = _human_age(now - float(i["completed_at"]))
        return render_template_string(
            _TEMPLATE, open_items=open_items, done_items=done_items
        )

    @bp.post("/add")
    def add() -> Any:
        text = (request.form.get("text") or "").strip()
        if not text:
            return redirect("/plugins/todo/")
        path = _store_path()
        items = _read_and_prune(path)
        items.append(
            {
                "id": uuid.uuid4().hex[:12],
                "text": text[:200],
                "created_at": int(time.time()),
            }
        )
        _save(path, items)
        return redirect("/plugins/todo/")

    @bp.post("/done/<item_id>")
    def done(item_id: str) -> Any:
        path = _store_path()
        items = _read_and_prune(path)
        for item in items:
            if item.get("id") == item_id and not item.get("completed_at"):
                item["completed_at"] = int(time.time())
                break
        _save(path, items)
        return redirect("/plugins/todo/")

    @bp.post("/undone/<item_id>")
    def undone(item_id: str) -> Any:
        path = _store_path()
        items = _read_and_prune(path)
        for item in items:
            if item.get("id") == item_id and item.get("completed_at"):
                item.pop("completed_at", None)
                break
        _save(path, items)
        return redirect("/plugins/todo/")

    @bp.post("/delete/<item_id>")
    def delete(item_id: str) -> Any:
        path = _store_path()
        items = [i for i in _read_and_prune(path) if i.get("id") != item_id]
        _save(path, items)
        return redirect("/plugins/todo/")

    return bp

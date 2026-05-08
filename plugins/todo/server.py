"""Todo state + admin blueprint.

State lives at ``data/plugins/todo/items.json`` (the loader's data_dir).
Items are JSON: {id, text, created_at}. Marking an item done removes it
(auto-prune is built in).
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from flask import Blueprint, current_app, redirect, render_template_string, request

_ITEMS_FILE = "items.json"


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


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    path = Path(ctx["data_dir"]) / _ITEMS_FILE
    return {"items": _load(path)}


_TEMPLATE = """
<!doctype html>
<html><head>
  <meta charset="utf-8">
  <title>Todo — Inky Dash</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="/static/icons/phosphor.css">
  <script type="module" src="/static/dist/_components.js"></script>
  <style>
    :root {
      --id-bg: #fbf7f1; --id-fg: #1a1612; --id-fg-soft: #5a4f44;
      --id-surface: #ffffff; --id-surface2: #f5e8d8; --id-divider: #c8b89b;
      --id-accent: #d97757; --id-accent-soft: #aa5a3f; --id-danger: #c97c70;
      --id-ok: #7da670;
    }
    body {
      font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
      margin: 0; background: var(--id-bg); color: var(--id-fg);
    }
    .container { max-width: 540px; margin: 0 auto; padding: 24px 16px 48px; }
    h1 { font-size: 22px; margin: 0 0 16px; }
    form.add { display: flex; gap: 8px; margin-bottom: 24px; }
    form.add input[type=text] {
      flex: 1; padding: 10px 12px; border: 1px solid var(--id-divider);
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
    ul.items { list-style: none; padding: 0; margin: 0; background: var(--id-surface); border: 1px solid var(--id-divider); border-radius: 8px; overflow: hidden; }
    ul.items li {
      display: flex; align-items: center; gap: 12px;
      padding: 12px 14px; border-bottom: 1px solid var(--id-divider);
    }
    ul.items li:last-child { border-bottom: 0; }
    ul.items li form { display: contents; }
    ul.items li button {
      padding: 6px 12px; border: 1px solid var(--id-divider);
      border-radius: 6px; background: var(--id-surface); font: inherit;
      font-size: 13px; cursor: pointer; display: inline-flex; align-items: center; gap: 4px;
    }
    ul.items li button:hover { background: var(--id-surface2); }
    .text { flex: 1; }
    .empty {
      color: var(--id-fg-soft); font-style: italic; padding: 32px 16px;
      text-align: center; background: var(--id-surface);
      border: 1px dashed var(--id-divider); border-radius: 8px;
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
    {% if items %}
    <ul class="items">
      {% for item in items %}
      <li>
        <span class="text">{{ item.text }}</span>
        <form method="post" action="/plugins/todo/remove/{{ item.id }}">
          <button type="submit"><i class="ph ph-check"></i> Done</button>
        </form>
      </li>
      {% endfor %}
    </ul>
    {% else %}
    <p class="empty">All done. Add an item above.</p>
    {% endif %}
  </div>
</body></html>
"""


def blueprint() -> Blueprint:
    bp = Blueprint("todo_admin", __name__)

    @bp.get("/")
    def index() -> str:
        return render_template_string(_TEMPLATE, items=_load(_store_path()))

    @bp.post("/add")
    def add() -> Any:
        text = (request.form.get("text") or "").strip()
        if not text:
            return redirect("/plugins/todo/")
        path = _store_path()
        items = _load(path)
        items.append(
            {
                "id": uuid.uuid4().hex[:12],
                "text": text[:200],
                "created_at": int(time.time()),
            }
        )
        _save(path, items)
        return redirect("/plugins/todo/")

    @bp.post("/remove/<item_id>")
    def remove(item_id: str) -> Any:
        path = _store_path()
        items = [i for i in _load(path) if i.get("id") != item_id]
        _save(path, items)
        return redirect("/plugins/todo/")

    return bp

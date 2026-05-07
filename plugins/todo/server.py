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
<title>Todo</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body { font: 16px/1.5 system-ui, -apple-system, sans-serif; max-width: 540px; margin: 24px auto; padding: 0 16px; color: #1a1612; }
  h1 { font-size: 20px; margin: 0 0 16px; }
  form.add { display: flex; gap: 8px; margin-bottom: 24px; }
  form.add input[type=text] { flex: 1; padding: 10px 12px; border: 1px solid #c8b89b; border-radius: 6px; font: inherit; min-height: 44px; box-sizing: border-box; }
  form.add button { padding: 0 16px; min-height: 44px; border: 0; border-radius: 6px; background: #d97757; color: white; font: inherit; font-weight: 600; cursor: pointer; }
  ul.items { list-style: none; padding: 0; margin: 0; }
  ul.items li { display: flex; align-items: center; gap: 12px; padding: 12px 0; border-bottom: 1px solid #ead9bc; }
  ul.items li form { display: contents; }
  ul.items li button { padding: 6px 12px; border: 1px solid #c8b89b; border-radius: 6px; background: white; font: inherit; font-size: 13px; cursor: pointer; }
  ul.items li button:hover { background: #f5e8d8; }
  .text { flex: 1; }
  .empty { color: #5a4f44; font-style: italic; padding: 16px 0; }
  a.back { font-size: 13px; color: #5a4f44; text-decoration: none; }
  a.back:hover { color: #d97757; }
</style>
</head><body>
<a class="back" href="/editor">← back to editor</a>
<h1>Todo</h1>
<form class="add" method="post" action="/plugins/todo/add">
  <input type="text" name="text" placeholder="What needs doing?" autofocus required maxlength="200">
  <button type="submit">Add</button>
</form>
{% if items %}
<ul class="items">
  {% for item in items %}
  <li>
    <span class="text">{{ item.text }}</span>
    <form method="post" action="/plugins/todo/remove/{{ item.id }}">
      <button type="submit">Done</button>
    </form>
  </li>
  {% endfor %}
</ul>
{% else %}
<p class="empty">No items. Add one above.</p>
{% endif %}
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

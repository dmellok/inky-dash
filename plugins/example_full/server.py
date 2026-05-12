"""Full example plugin — server-side surface.

Three optional plugin hooks are demonstrated here:

1. ``fetch(options, settings, *, ctx)`` — called once per render to produce
   the ``ctx.data`` blob that the client receives. Use this for anything
   that needs Python: HTTP requests, disk reads, computed values that are
   easier server-side.

2. ``choices(name)`` — supplies the values for any ``cell_option`` whose
   manifest entry uses ``"choices_from": "<name>"``. The editor calls this
   at edit-time so dynamic dropdowns (e.g. "list of folders", "list of
   home-assistant entities") stay in sync with the underlying state.

3. ``blueprint()`` — returns a Flask blueprint mounted at
   ``/plugins/<id>/``. Use it for admin pages the widget needs but doesn't
   want to bake into the editor (file uploads, multi-step configuration,
   things that need their own URL).

Keep ``fetch()`` fast — it runs on every render. Cache or pre-compute
anything expensive. The widget render loop won't wait forever on you.
"""

from __future__ import annotations

import time
from typing import Any

from flask import Blueprint, render_template_string

# A toy in-memory data source so the dynamic dropdown has something to
# return without external network calls. In a real plugin this is where
# you'd hit an API, read a JSON file from ``ctx["data_dir"]``, etc.
_CATEGORIES = [
    {"value": "alpha", "label": "Alpha"},
    {"value": "beta", "label": "Beta"},
    {"value": "gamma", "label": "Gamma"},
]


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    """Produce the ``ctx.data`` payload for the client renderer.

    Args:
      options: the cell's saved options (matches the manifest's
        ``cell_options`` keys). Editor-provided values arrive here.
      settings: plugin-level settings from /settings (matches the manifest's
        ``settings`` keys). Secrets are real values here — they only get
        masked when crossing back over the wire to the editor.
      ctx: extras the loader provides. ``ctx["data_dir"]`` is a
        plugin-private Path under data/plugins/<id>/. ``ctx["panel"]`` has
        panel dimensions; ``ctx["preview"]`` is True during /editor previews.

    Returns:
      A dict — anything JSON-serialisable is fine. It lands as ``ctx.data``
      in the client renderer.
    """
    count = max(1, min(12, int(options.get("count") or 1)))
    show_debug = bool(settings.get("show_debug"))
    items = [
        {
            "id": i,
            "label": f"Item {i:02d}",
            "value": round(50 + 30 * (i / count), 1),
        }
        for i in range(1, count + 1)
    ]
    payload: dict[str, Any] = {
        "items": items,
        "fetched_at": int(time.time()),
        "category_label": next(
            (c["label"] for c in _CATEGORIES if c["value"] == options.get("category")),
            None,
        ),
    }
    if show_debug:
        payload["debug"] = {
            "options": dict(options),
            # Mask the secret here too — defence in depth.
            "settings_keys": sorted(settings.keys()),
            "data_dir": str(ctx.get("data_dir")),
        }
    return payload


def choices(name: str) -> list[dict[str, Any]]:
    """Resolver for ``cell_options[*].choices_from``. The editor calls
    GET /api/plugins/<plugin_id>/choices/<name> when populating the dropdown.

    Return a list of ``{"value": ..., "label": ...}`` dicts. Anything else
    is ignored.
    """
    if name == "categories":
        return _CATEGORIES
    return []


_ADMIN_TEMPLATE = """
<!doctype html>
<html lang="en"><head>
  <meta charset="utf-8">
  <title>Full example — Inky Dash</title>
  <link rel="stylesheet" href="/static/style/tokens.css">
  <script type="module" src="/static/dist/_components.js"></script>
  <style>
    body { font: 16px/1.5 system-ui, -apple-system, Roboto, sans-serif;
           background: var(--id-bg, #fff); color: var(--id-fg, #1a1612); }
    .container { max-width: 720px; margin: 0 auto; padding: 24px 16px 48px; }
    h1 { font-size: 22px; margin: 0 0 12px; }
    p.lede { color: var(--id-fg-soft, #5a4f44); margin: 0 0 16px; }
    code { background: var(--id-surface2, #f5e8d8); padding: 2px 6px; border-radius: 4px; }
    ul { line-height: 1.7; }
  </style>
</head><body>
  <id-nav></id-nav>
  <div class="container">
    <h1>Full example — admin page</h1>
    <p class="lede">
      Anything you put under a plugin's <code>blueprint()</code> mounts at
      <code>/plugins/&lt;id&gt;/</code>. This is the place for upload forms,
      multi-step configuration, integration-test panels, or whatever else
      doesn't belong in the per-cell editor sidebar.
    </p>
    <p>Categories currently in the dynamic dropdown:</p>
    <ul>
      {% for c in categories %}
      <li><strong>{{ c.label }}</strong> — value <code>{{ c.value }}</code></li>
      {% endfor %}
    </ul>
    <p>
      The plugin contract lives in
      <a href="/docs/v4-plugins.md"><code>docs/v4-plugins.md</code></a>;
      the usage tutorial lives in
      <a href="https://github.com/dmellok/inky-dash/wiki/Writing-a-plugin">
        the wiki
      </a>.
    </p>
  </div>
</body></html>
"""


def blueprint() -> Blueprint:
    """Optional Flask blueprint mounted at /plugins/<id>/."""
    bp = Blueprint("example_full_admin", __name__)

    @bp.get("/")
    def index() -> str:
        return render_template_string(_ADMIN_TEMPLATE, categories=_CATEGORIES)

    return bp

"""Public Transport Victoria (PTV) Timetable API client.

The PTV API requires an HMAC-SHA1 signature of every request path. The
signed path is::

    <path>?devid=<devid>

…and the signature is the uppercase hex of HMAC-SHA1 keyed with the
``api_key`` secret. The signature is then appended to the URL as
``&signature=<sig>``.

We expose two things:

1. ``fetch()`` — fetches the next departures for the configured
   stop / route_type / direction. Used at render time.
2. A small admin Flask blueprint at ``/plugins/ptv/`` that lets users
   look up stop IDs by name. The PTV ``/v3/search/{term}`` endpoint
   returns stops + routes + directions, which we render in a table so
   the user can copy the right stop_id back into their cell options.

Tokens are stored under plugin settings (both marked secret).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from typing import Any

from flask import Blueprint, current_app, render_template_string, request

PTV_BASE = "https://timetableapi.ptv.vic.gov.au"
ROUTE_TYPE_LABELS: dict[int, str] = {
    0: "Train",
    1: "Tram",
    2: "Bus",
    3: "V/Line",
    4: "Night Bus",
}


# ---------------------------------------------------------------------------
# Signed request helper
# ---------------------------------------------------------------------------


def _signed_url(path_with_query: str, devid: str, api_key: str) -> str:
    """Append devid + signature to a path. ``path_with_query`` is everything
    after the host, with ``?`` already in it if there were leading query
    params. We always append ``devid`` ourselves."""
    sep = "&" if "?" in path_with_query else "?"
    signed_path = f"{path_with_query}{sep}devid={urllib.parse.quote(devid)}"
    signature = (
        hmac.new(api_key.encode("utf-8"), signed_path.encode("utf-8"), hashlib.sha1)
        .hexdigest()
        .upper()
    )
    return f"{PTV_BASE}{signed_path}&signature={signature}"


def _get_json(path_with_query: str, devid: str, api_key: str) -> dict[str, Any]:
    url = _signed_url(path_with_query, devid, api_key)
    req = urllib.request.Request(url, headers={"User-Agent": "inky-dash/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# fetch()
# ---------------------------------------------------------------------------


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    devid = (settings.get("devid") or "").strip()
    api_key = (settings.get("api_key") or "").strip()
    if not devid or not api_key:
        return {"error": "Set the PTV devid + api_key in plugin settings."}

    stop_id = (options.get("stop_id") or "").strip()
    if not stop_id:
        return {"error": "Set a stop_id in the cell options."}

    try:
        route_type = int(options.get("route_type", 0) or 0)
    except (TypeError, ValueError):
        route_type = 0
    try:
        max_results = max(1, min(int(options.get("max_results", 6) or 6), 20))
    except (TypeError, ValueError):
        max_results = 6
    title = (options.get("title") or "").strip()

    path = (
        f"/v3/departures/route_type/{route_type}/stop/"
        f"{urllib.parse.quote(stop_id)}"
        f"?max_results={max_results}&expand=route&expand=run&expand=stop&expand=direction"
        f"&include_cancelled=false"
    )
    try:
        payload = _get_json(path, devid, api_key)
    except urllib.error.HTTPError as err:
        return {"error": f"PTV HTTP {err.code}: {err.reason}"}
    except Exception as err:  # noqa: BLE001
        return {"error": f"PTV: {type(err).__name__}: {err}"}

    departures_raw = payload.get("departures") or []
    routes = payload.get("routes") or {}
    runs = payload.get("runs") or {}
    stops = payload.get("stops") or {}
    directions = payload.get("directions") or {}

    stop = stops.get(stop_id) or next(iter(stops.values()), None) or {}
    stop_name = stop.get("stop_name") or f"Stop {stop_id}"

    now = datetime.now(UTC)
    departures: list[dict[str, Any]] = []
    for d in departures_raw[:max_results]:
        scheduled = d.get("scheduled_departure_utc")
        estimated = d.get("estimated_departure_utc")
        when_iso = estimated or scheduled
        if not when_iso:
            continue
        try:
            when = datetime.fromisoformat(when_iso.replace("Z", "+00:00"))
        except ValueError:
            continue
        delta_min = round((when - now).total_seconds() / 60)
        route_info = routes.get(str(d.get("route_id"))) or {}
        run_info = runs.get(str(d.get("run_ref"))) or runs.get(d.get("run_ref")) or {}
        direction_info = directions.get(str(d.get("direction_id"))) or {}
        destination = run_info.get("destination_name") or direction_info.get("direction_name") or ""
        departures.append(
            {
                "route_name": route_info.get("route_name", ""),
                "route_number": route_info.get("route_number", ""),
                "destination": destination,
                "scheduled_local": when.astimezone().strftime("%H:%M"),
                "scheduled_iso": when_iso,
                "in_minutes": delta_min,
                "is_estimated": bool(estimated),
                "platform": d.get("platform_number") or "",
            }
        )

    return {
        "stop_name": stop_name,
        "title": title,
        "route_type_label": ROUTE_TYPE_LABELS.get(route_type, "Transit"),
        "departures": departures,
        "generated_at": int(time.time()),
    }


# ---------------------------------------------------------------------------
# Admin page — stop ID lookup
# ---------------------------------------------------------------------------


_TEMPLATE = """
<!doctype html>
<html lang="en"><head>
  <meta charset="utf-8">
  <title>PTV stop lookup — Inky Dash</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="/static/icons/phosphor.css">
  <link rel="stylesheet" href="/static/style/tokens.css">
  <script>
    (function () {
      try {
        var theme = localStorage.getItem('inky_theme') || 'auto';
        var accent = localStorage.getItem('inky_accent');
        var root = document.documentElement;
        var isDark = theme === 'dark' ||
          (theme === 'auto' && window.matchMedia &&
           window.matchMedia('(prefers-color-scheme: dark)').matches);
        if (isDark) root.dataset.theme = 'dark';
        else root.removeAttribute('data-theme');
        if (accent) root.style.setProperty('--id-accent', accent);
      } catch (_) {}
    })();
  </script>
  <script type="module" src="/static/dist/_components.js"></script>
  <style>
    body { font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
    .container { max-width: 720px; margin: 0 auto; padding: 24px 16px 48px; }
    h1 { font-size: 22px; margin: 0 0 12px; }
    p.lede { color: var(--id-fg-soft); margin: 0 0 16px; }
    form.search {
      display: flex; gap: 8px; margin-bottom: 24px;
    }
    form.search input {
      flex: 1; padding: 10px 12px;
      border: 2px solid var(--id-divider); border-radius: 6px;
      background: var(--id-surface); color: var(--id-fg);
      font: inherit; min-height: 44px; box-sizing: border-box;
    }
    form.search button {
      padding: 0 16px; min-height: 44px; border: 0; border-radius: 6px;
      background: var(--id-accent); color: white; font: inherit; font-weight: 600;
      cursor: pointer;
    }
    table {
      width: 100%; border-collapse: collapse; font-size: 14px;
      background: var(--id-surface);
      border: 2px solid var(--id-divider); border-radius: 8px; overflow: hidden;
    }
    th, td {
      padding: 10px 12px; text-align: left; border-bottom: 2px solid var(--id-divider);
    }
    th {
      background: var(--id-surface2); font-size: 12px;
      text-transform: uppercase; letter-spacing: 0.05em;
    }
    tr:last-child td { border-bottom: 0; }
    .id { font-family: ui-monospace, "SF Mono", Menlo, monospace; }
    .badge {
      display: inline-block; padding: 2px 8px; border-radius: 999px;
      background: var(--id-surface2); font-size: 11px; font-weight: 600;
      text-transform: uppercase; letter-spacing: 0.05em; color: var(--id-fg-soft);
    }
    .copy {
      border: 0; background: var(--id-accent); color: white;
      padding: 4px 8px; border-radius: 4px; font: inherit; font-size: 12px;
      cursor: pointer; font-weight: 600;
    }
    .empty {
      padding: 32px; text-align: center; color: var(--id-fg-soft);
      background: var(--id-surface); border: 2px dashed var(--id-divider);
      border-radius: 8px; font-style: italic;
    }
    .err {
      padding: 12px 14px; border-radius: 6px; background: rgb(201 124 112 / 0.1);
      border: 2px solid var(--id-danger, #c97c70); color: var(--id-danger);
      margin-bottom: 16px;
    }
  </style>
</head><body>
  <id-nav></id-nav>
  <div class="container">
    <h1><i class="ph ph-train" style="color: var(--id-accent);"></i> PTV stop lookup</h1>
    <p class="lede">
      Type a station, stop, or area name (e.g. <em>Flinders Street</em>,
      <em>Box Hill</em>, <em>tram 96</em>) to find the stop ID you'll need in
      the cell options.
    </p>
    <form class="search" method="get" action="/plugins/ptv/">
      <input type="text" name="q" value="{{ q or '' }}" placeholder="Search PTV stops…" autofocus>
      <button type="submit"><i class="ph ph-magnifying-glass"></i> Search</button>
    </form>
    {% if error %}
      <div class="err">{{ error }}</div>
    {% endif %}
    {% if q and not error %}
      {% if stops %}
        <table>
          <thead><tr>
            <th>Stop name</th><th>Mode</th><th>Stop ID</th><th></th>
          </tr></thead>
          <tbody>
            {% for s in stops %}
            <tr>
              <td>{{ s.name }}{% if s.suburb %} <span class="badge">{{ s.suburb }}</span>{% endif %}</td>
              <td><span class="badge">{{ s.route_type_label }}</span></td>
              <td class="id">{{ s.id }}</td>
              <td><button class="copy" type="button"
                  onclick="navigator.clipboard.writeText('{{ s.id }}'); this.textContent='copied'; setTimeout(()=>this.textContent='copy id', 1500);">copy id</button></td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      {% else %}
        <div class="empty">No stops matched “{{ q }}”.</div>
      {% endif %}
    {% endif %}
  </div>
</body></html>
"""


def blueprint() -> Blueprint:
    bp = Blueprint("ptv_admin", __name__)

    def _settings() -> dict[str, str]:
        # Late lookup so the admin page works even if creds get rotated.
        store = current_app.config["SETTINGS_STORE"]
        return store.get("ptv")

    @bp.get("/")
    def index() -> str:
        q = (request.args.get("q") or "").strip()
        if not q:
            return render_template_string(_TEMPLATE, q="", stops=[], error=None)
        s = _settings()
        devid = (s.get("devid") or "").strip()
        api_key = (s.get("api_key") or "").strip()
        if not devid or not api_key:
            return render_template_string(
                _TEMPLATE,
                q=q,
                stops=[],
                error="Set the PTV devid + api_key in /settings before searching.",
            )
        path = f"/v3/search/{urllib.parse.quote(q)}?include_outlets=false"
        try:
            payload = _get_json(path, devid, api_key)
        except urllib.error.HTTPError as err:
            return render_template_string(
                _TEMPLATE, q=q, stops=[], error=f"PTV HTTP {err.code}: {err.reason}"
            )
        except Exception as err:  # noqa: BLE001
            return render_template_string(
                _TEMPLATE, q=q, stops=[], error=f"PTV: {type(err).__name__}: {err}"
            )
        stops = [
            {
                "id": st.get("stop_id"),
                "name": st.get("stop_name"),
                "suburb": st.get("stop_suburb"),
                "route_type_label": ROUTE_TYPE_LABELS.get(st.get("route_type", -1), "?"),
            }
            for st in (payload.get("stops") or [])[:30]
        ]
        return render_template_string(_TEMPLATE, q=q, stops=stops, error=None)

    return bp

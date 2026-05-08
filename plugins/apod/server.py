"""NASA APOD widget — Astronomy Picture of the Day.

Calls api.nasa.gov/planetary/apod. If the most recent entry's media_type is
"video" (which APOD does occasionally), walks back day-by-day until it finds
an image, capping the lookback so a long video streak can't trigger a
network storm. Cached to disk so the panel can re-render without re-hitting
the rate-limited API.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

CACHE_TTL = 60 * 60  # 1 hour
LOOKBACK_DAYS = 14   # how far to search back if today's APOD is a video
DEMO_KEY = "DEMO_KEY"


def _api_request(api_key: str, when: date | None = None) -> dict[str, Any]:
    params = {"api_key": api_key, "thumbs": "true"}
    if when is not None:
        params["date"] = when.isoformat()
    url = "https://api.nasa.gov/planetary/apod?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "inky-dash/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _pick_image_url(entry: dict[str, Any]) -> str | None:
    """Prefer the high-res `hdurl` when present, fall back to `url`."""
    if entry.get("media_type") != "image":
        return None
    return entry.get("hdurl") or entry.get("url")


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    api_key = (settings.get("api_key") or DEMO_KEY).strip() or DEMO_KEY

    data_dir = Path(ctx["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)
    cache = data_dir / "apod.json"
    if cache.exists() and time.time() - cache.stat().st_mtime < CACHE_TTL:
        try:
            return json.loads(cache.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    today = datetime.now(UTC).date()
    chosen: dict[str, Any] | None = None
    last_err: str | None = None

    # Walk back day-by-day until we land on an image entry. Capped at
    # LOOKBACK_DAYS so a freak video streak doesn't hammer the API.
    for offset in range(LOOKBACK_DAYS):
        when: date | None = today - timedelta(days=offset) if offset > 0 else None
        try:
            entry = _api_request(api_key, when)
        except urllib.error.HTTPError as err:
            # Auth / rate-limit / future-date — bail with the message rather
            # than retry a date that won't ever resolve.
            last_err = f"HTTP {err.code}: {err.reason}"
            break
        except Exception as err:  # noqa: BLE001 — every other transport failure
            last_err = f"{type(err).__name__}: {err}"
            break

        url = _pick_image_url(entry)
        if url:
            chosen = entry
            chosen["_image_url"] = url
            break

    if chosen is None:
        return {
            "error": last_err or f"No APOD image found in the last {LOOKBACK_DAYS} days.",
            "url": None,
        }

    result = {
        "url": chosen["_image_url"],
        "title": chosen.get("title", ""),
        "date": chosen.get("date", ""),
        "copyright": chosen.get("copyright", "").strip(),
        "fetched_at": int(time.time()),
    }
    cache.write_text(json.dumps(result))
    return result

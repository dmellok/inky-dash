"""xkcd widget. xkcd's official JSON endpoints:
  - https://xkcd.com/info.0.json           — latest
  - https://xkcd.com/<num>/info.0.json     — specific number
"""

from __future__ import annotations

import json
import random
import time
import urllib.request
from pathlib import Path
from typing import Any

CACHE_TTL = 60 * 60 * 6  # 6 hours; xkcd updates 3x/week


def _fetch(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "inky-dash/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    mode = options.get("comic", "latest")
    number = int(options.get("number", 1) or 1)

    data_dir = Path(ctx["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)
    # Random mode: don't cache (defeats the purpose). Other modes use cache.
    cache_key = f"xkcd_{mode}_{number}"
    cache = data_dir / f"{cache_key}.json"
    if mode != "random" and cache.exists() and time.time() - cache.stat().st_mtime < CACHE_TTL:
        try:
            return json.loads(cache.read_text())
        except (json.JSONDecodeError, OSError):
            pass

    try:
        if mode == "specific" and number > 0:
            entry = _fetch(f"https://xkcd.com/{number}/info.0.json")
        elif mode == "random":
            # First fetch latest to learn the upper bound, then pick.
            latest = _fetch("https://xkcd.com/info.0.json")
            picked = random.randint(1, max(1, int(latest.get("num", 1))))
            entry = (
                latest if picked == latest.get("num")
                else _fetch(f"https://xkcd.com/{picked}/info.0.json")
            )
        else:
            entry = _fetch("https://xkcd.com/info.0.json")
    except Exception as err:  # noqa: BLE001
        return {"error": f"{type(err).__name__}: {err}"}

    img_url = entry.get("img", "")
    if img_url.startswith("http://"):
        # xkcd serves https; force it so embedded images load on https pages.
        img_url = "https://" + img_url[len("http://") :]

    result = {
        "num": entry.get("num"),
        "title": entry.get("safe_title") or entry.get("title", ""),
        "img": img_url,
        "alt": entry.get("alt", ""),
        "date": f"{entry.get('year', '')}-{entry.get('month', '01').zfill(2)}-{entry.get('day', '01').zfill(2)}",
        "fetched_at": int(time.time()),
    }
    if mode != "random":
        cache.write_text(json.dumps(result))
    return result

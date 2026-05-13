"""Trakt watchlist → random poster widget.

Two upstream APIs:

  * **Trakt** (api.trakt.tv) — source of truth for the watchlist itself.
    A user's public watchlist is readable with just a ``trakt-api-key``
    header (the OAuth client_id from a personal-use app). No login flow
    required as long as the user's profile is public.
  * **TMDB** (api.themoviedb.org) — poster lookup keyed off the
    ``ids.tmdb`` field that Trakt returns for each watchlist entry.

Caching:
  * The full watchlist is cached on disk for one hour. Random selection
    happens on every fetch — so a fresh poster each push without
    hammering Trakt.
  * Each TMDB poster_path is cached indefinitely (they're stable for
    the lifetime of a given TMDB id) under ``data_dir/posters.json``.
"""

from __future__ import annotations

import json
import logging
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

TRAKT_API_BASE = "https://api.trakt.tv"
TMDB_API_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w780"

WATCHLIST_TTL = 60 * 60  # 1 hour
NETWORK_TIMEOUT = 15
USER_AGENT = "inky-dash/1.0 (trakt-watchlist-widget)"

# We retry a few random picks if the first choice has no poster available
# on TMDB — some indie titles slip through with no image. Capped low so
# a deeply broken watchlist surfaces an error fast rather than hanging.
MAX_PICK_RETRIES = 8


def _trakt_watchlist(username: str, client_id: str, media_type: str) -> list[dict[str, Any]]:
    """Fetch the public watchlist for ``username``. ``media_type`` is one
    of 'movies', 'shows', or 'all'. Raises on HTTP / decode errors."""
    if media_type == "all":
        path = f"/users/{urllib.parse.quote(username)}/watchlist"
    else:
        # Trakt expects singular path component (movies/shows).
        path = f"/users/{urllib.parse.quote(username)}/watchlist/{media_type}"
    url = TRAKT_API_BASE + path + "?extended=min"
    req = urllib.request.Request(
        url,
        headers={
            "Content-Type": "application/json",
            "trakt-api-version": "2",
            "trakt-api-key": client_id,
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(req, timeout=NETWORK_TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"unexpected Trakt response shape: {type(data).__name__}")
    return data


def _normalise_entry(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Flatten one Trakt watchlist entry into ``{kind, title, year, tmdb_id}``.
    Returns None if the entry has no TMDB id (no poster path possible)."""
    # Trakt nests the metadata under "movie" or "show" depending on type.
    for kind in ("movie", "show"):
        body = raw.get(kind)
        if isinstance(body, dict):
            ids = body.get("ids") or {}
            tmdb_id = ids.get("tmdb")
            if not isinstance(tmdb_id, int):
                return None
            return {
                "kind": kind,
                "title": body.get("title", ""),
                "year": body.get("year"),
                "tmdb_id": tmdb_id,
            }
    return None


def _tmdb_poster_path(kind: str, tmdb_id: int, api_key: str) -> str | None:
    """Look up the canonical poster_path for one TMDB entry. Returns the
    leading-slash path string (e.g. "/abc123.jpg") that we'll suffix onto
    the TMDB image CDN base, or None if no poster is on file."""
    tmdb_kind = "movie" if kind == "movie" else "tv"
    url = (
        f"{TMDB_API_BASE}/{tmdb_kind}/{tmdb_id}"
        f"?api_key={urllib.parse.quote(api_key)}&language=en-US"
    )
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=NETWORK_TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not isinstance(data, dict):
        return None
    path = data.get("poster_path")
    if isinstance(path, str) and path:
        return path
    return None


class _PosterCache:
    """Disk-backed poster_path cache keyed by 'movie:42' / 'tv:1399'."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._data: dict[str, str] = self._read()

    def _read(self) -> dict[str, str]:
        if not self._path.exists():
            return {}
        try:
            raw = json.loads(self._path.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
        if not isinstance(raw, dict):
            return {}
        return {k: v for k, v in raw.items() if isinstance(v, str)}

    def _write(self) -> None:
        try:
            self._path.write_text(json.dumps(self._data, sort_keys=True))
        except OSError as err:
            logger.warning("trakt_watchlist: poster cache write failed: %s", err)

    def get(self, kind: str, tmdb_id: int) -> str | None:
        return self._data.get(f"{kind}:{tmdb_id}")

    def set(self, kind: str, tmdb_id: int, path: str) -> None:
        self._data[f"{kind}:{tmdb_id}"] = path
        self._write()


def _load_watchlist(
    data_dir: Path,
    username: str,
    client_id: str,
    media_type: str,
    rng: random.Random,
) -> tuple[list[dict[str, Any]], str | None]:
    """Return the cached watchlist (refreshing if stale) + an optional
    note about which side of the cache was used. Note is None on a clean
    fresh fetch; otherwise something like 'stale: HTTP 502'."""
    cache_path = data_dir / "watchlist.json"
    note: str | None = None
    cached: list[dict[str, Any]] = []
    cached_fresh = False
    if cache_path.exists():
        try:
            raw = json.loads(cache_path.read_text())
        except (json.JSONDecodeError, OSError):
            raw = {}
        if isinstance(raw, dict):
            items = raw.get("items")
            fetched_at = raw.get("fetched_at", 0)
            if (
                isinstance(items, list)
                and raw.get("media_type") == media_type
                and raw.get("username") == username
                and isinstance(fetched_at, int | float)
            ):
                cached = items
                cached_fresh = (time.time() - fetched_at) < WATCHLIST_TTL

    if cached_fresh:
        return cached, None

    try:
        raw_entries = _trakt_watchlist(username, client_id, media_type)
    except urllib.error.HTTPError as err:
        if cached:
            return cached, f"stale: HTTP {err.code}"
        raise
    except Exception as err:  # noqa: BLE001
        if cached:
            return cached, f"stale: {type(err).__name__}"
        raise

    items: list[dict[str, Any]] = []
    for entry in raw_entries:
        if not isinstance(entry, dict):
            continue
        flat = _normalise_entry(entry)
        if flat is not None:
            items.append(flat)
    cache_path.write_text(
        json.dumps(
            {
                "username": username,
                "media_type": media_type,
                "items": items,
                "fetched_at": int(time.time()),
            }
        )
    )
    _ = rng  # rng is unused here; caller picks
    return items, note


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    client_id = (settings.get("trakt_client_id") or "").strip()
    tmdb_key = (settings.get("tmdb_api_key") or "").strip()
    username = (settings.get("trakt_username") or "").strip()
    media_type = options.get("media_type") or "movies"
    if media_type not in {"movies", "shows", "all"}:
        media_type = "movies"

    if not client_id or not tmdb_key or not username:
        missing = [
            label
            for label, value in (
                ("Trakt client_id", client_id),
                ("TMDB API key", tmdb_key),
                ("Trakt username", username),
            )
            if not value
        ]
        return {
            "error": "Missing in /settings: " + ", ".join(missing),
            "url": None,
        }

    data_dir = Path(ctx["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random()

    try:
        items, note = _load_watchlist(data_dir, username, client_id, media_type, rng)
    except urllib.error.HTTPError as err:
        return {"error": f"Trakt HTTP {err.code}: {err.reason}", "url": None}
    except Exception as err:  # noqa: BLE001
        return {"error": f"Trakt fetch failed: {type(err).__name__}: {err}", "url": None}

    if not items:
        return {
            "error": f"Watchlist is empty for {username} ({media_type}).",
            "url": None,
        }

    poster_cache = _PosterCache(data_dir / "posters.json")

    # Try a handful of random picks before giving up — some items have no
    # poster on TMDB and we'd rather show a different one than fail.
    pool = list(items)
    rng.shuffle(pool)
    last_err: str | None = None
    for pick in pool[:MAX_PICK_RETRIES]:
        path = poster_cache.get(pick["kind"], pick["tmdb_id"])
        if path is None:
            try:
                path = _tmdb_poster_path(pick["kind"], pick["tmdb_id"], tmdb_key)
            except urllib.error.HTTPError as err:
                last_err = f"TMDB HTTP {err.code}"
                continue
            except Exception as err:  # noqa: BLE001
                last_err = f"TMDB {type(err).__name__}"
                continue
            if path is None:
                continue
            poster_cache.set(pick["kind"], pick["tmdb_id"], path)
        return {
            "url": TMDB_IMAGE_BASE + path,
            "title": pick["title"],
            "year": pick["year"],
            "kind": pick["kind"],
            "tmdb_id": pick["tmdb_id"],
            "watchlist_size": len(items),
            "note": note,
            "fetched_at": int(time.time()),
        }

    return {
        "error": last_err or "No items in the watchlist had a TMDB poster.",
        "url": None,
    }

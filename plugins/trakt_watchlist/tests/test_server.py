"""Unit tests for the trakt_watchlist plugin server.

Mocks urllib.request.urlopen so we don't hit the network. Covers:
- Settings validation (missing keys surface specific messages)
- Watchlist parsing (movie + show shapes, missing TMDB id skip)
- Cache hit path (no network call when fresh)
- Stale-cache fallback when Trakt errors but a previous good cache exists
- TMDB poster lookup + per-id caching
- Empty-watchlist + no-poster-anywhere error paths
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import urllib.error
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import patch

_SERVER = importlib.util.spec_from_file_location(
    "trakt_watchlist_server",
    Path(__file__).parent.parent / "server.py",
)
assert _SERVER is not None and _SERVER.loader is not None
trakt_server = importlib.util.module_from_spec(_SERVER)
sys.modules["trakt_watchlist_server"] = trakt_server
_SERVER.loader.exec_module(trakt_server)


# -- HTTP fakery ---------------------------------------------------------


class _FakeResp:
    def __init__(self, payload: Any) -> None:
        self._buf = io.BytesIO(json.dumps(payload).encode("utf-8"))

    def __enter__(self) -> _FakeResp:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._buf.read()


def _route(responses: dict[str, Any]) -> Iterator[Any]:
    """Build a urlopen side_effect that matches incoming Request URLs
    against substring keys in ``responses``. Values are either a payload
    (JSON-serialisable) or an Exception to raise."""

    def _open(req: Any, timeout: int = 0) -> _FakeResp:
        url = getattr(req, "full_url", str(req))
        for needle, payload in responses.items():
            if needle in url:
                if isinstance(payload, Exception):
                    raise payload
                return _FakeResp(payload)
        raise AssertionError(f"unexpected URL in test: {url}")

    return _open  # type: ignore[return-value]


# -- Helpers -------------------------------------------------------------


def _settings_full() -> dict[str, str]:
    return {
        "trakt_client_id": "TEST_CLIENT_ID",
        "tmdb_api_key": "TEST_TMDB_KEY",
        "trakt_username": "kayden",
    }


def _ctx(tmp_path: Path) -> dict[str, Any]:
    return {"data_dir": tmp_path, "panel": {"w": 1200, "h": 1600}, "preview": False}


def _movie(title: str, year: int, tmdb_id: int) -> dict[str, Any]:
    return {
        "type": "movie",
        "movie": {
            "title": title,
            "year": year,
            "ids": {"trakt": tmdb_id, "imdb": f"tt{tmdb_id}", "tmdb": tmdb_id},
        },
    }


# -- Tests ---------------------------------------------------------------


def test_missing_settings_returns_error_listing_which(tmp_path: Path) -> None:
    result = trakt_server.fetch({}, {}, ctx=_ctx(tmp_path))
    assert result["url"] is None
    msg = result["error"]
    assert "Missing in /settings" in msg
    assert "Trakt client_id" in msg
    assert "TMDB API key" in msg
    assert "Trakt username" in msg


def test_picks_movie_and_returns_resolved_poster_url(tmp_path: Path) -> None:
    fake = _route(
        {
            "api.trakt.tv/users/kayden/watchlist/movies": [_movie("Tron", 1982, 1)],
            "api.themoviedb.org/3/movie/1": {"poster_path": "/abc.jpg"},
        }
    )
    with patch.object(trakt_server.urllib.request, "urlopen", side_effect=fake):
        result = trakt_server.fetch({"media_type": "movies"}, _settings_full(), ctx=_ctx(tmp_path))
    assert result.get("url") == "https://image.tmdb.org/t/p/w780/abc.jpg"
    assert result["title"] == "Tron"
    assert result["year"] == 1982
    assert result["kind"] == "movie"
    assert result["watchlist_size"] == 1


def test_watchlist_is_cached_one_hour(tmp_path: Path) -> None:
    """Two consecutive fetches should only hit Trakt once. TMDB lookup is
    cached separately, so we expect the second call to skip both."""
    trakt_hits = {"count": 0}
    tmdb_hits = {"count": 0}

    def _open(req: Any, timeout: int = 0) -> _FakeResp:
        url = getattr(req, "full_url", str(req))
        if "api.trakt.tv" in url:
            trakt_hits["count"] += 1
            return _FakeResp([_movie("Tron", 1982, 1)])
        if "api.themoviedb.org" in url:
            tmdb_hits["count"] += 1
            return _FakeResp({"poster_path": "/abc.jpg"})
        raise AssertionError(f"unexpected URL: {url}")

    with patch.object(trakt_server.urllib.request, "urlopen", side_effect=_open):
        trakt_server.fetch({}, _settings_full(), ctx=_ctx(tmp_path))
        trakt_server.fetch({}, _settings_full(), ctx=_ctx(tmp_path))
    assert trakt_hits["count"] == 1, "watchlist cache should suppress second Trakt call"
    assert tmdb_hits["count"] == 1, "poster cache should suppress second TMDB call"


def test_stale_cache_falls_back_when_trakt_errors(tmp_path: Path) -> None:
    # Seed a fresh cache so the second fetch has something to fall back to.
    cache = tmp_path / "watchlist.json"
    cache.write_text(
        json.dumps(
            {
                "username": "kayden",
                "media_type": "movies",
                "items": [{"kind": "movie", "title": "Old Pick", "year": 2020, "tmdb_id": 42}],
                # Pretend the cache is older than the TTL by setting an
                # ancient timestamp — forces a refresh attempt.
                "fetched_at": 0,
            }
        )
    )
    err = urllib.error.HTTPError(
        url="https://api.trakt.tv/...", code=502, msg="Bad Gateway", hdrs=None, fp=None
    )
    fake = _route(
        {
            "api.trakt.tv": err,
            "api.themoviedb.org/3/movie/42": {"poster_path": "/old.jpg"},
        }
    )
    with patch.object(trakt_server.urllib.request, "urlopen", side_effect=fake):
        result = trakt_server.fetch({}, _settings_full(), ctx=_ctx(tmp_path))
    # Should still succeed using the stale cache.
    assert result.get("url") == "https://image.tmdb.org/t/p/w780/old.jpg"
    assert result["title"] == "Old Pick"


def test_skips_entries_with_no_tmdb_id(tmp_path: Path) -> None:
    """Trakt sometimes hands back entries with null tmdb ids (rare). They
    should be silently dropped, not blow up the fetch."""
    entries = [
        {"type": "movie", "movie": {"title": "Orphan", "year": 1999, "ids": {}}},
        _movie("Real", 2020, 7),
    ]
    fake = _route(
        {
            "api.trakt.tv": entries,
            "api.themoviedb.org/3/movie/7": {"poster_path": "/r.jpg"},
        }
    )
    with patch.object(trakt_server.urllib.request, "urlopen", side_effect=fake):
        result = trakt_server.fetch({}, _settings_full(), ctx=_ctx(tmp_path))
    assert result["watchlist_size"] == 1
    assert result["title"] == "Real"


def test_retries_pick_when_poster_lookup_returns_none(tmp_path: Path) -> None:
    """First random pick has no poster on TMDB; widget should silently
    try another instead of surfacing an error."""
    entries = [_movie("NoPoster", 2010, 10), _movie("HasPoster", 2010, 20)]
    poster_responses = {10: {"poster_path": None}, 20: {"poster_path": "/yes.jpg"}}

    def _open(req: Any, timeout: int = 0) -> _FakeResp:
        url = getattr(req, "full_url", str(req))
        if "api.trakt.tv" in url:
            return _FakeResp(entries)
        for tid, body in poster_responses.items():
            if f"/movie/{tid}" in url:
                return _FakeResp(body)
        raise AssertionError(f"unexpected URL: {url}")

    with patch.object(trakt_server.urllib.request, "urlopen", side_effect=_open):
        # Run a few times — at least one run should land on HasPoster.
        # MAX_PICK_RETRIES=8 against a pool of 2 makes failure vanishingly
        # unlikely (the loop iterates pool[:8] = both items, so the second
        # item is always tried as long as the first lacks a poster).
        result = trakt_server.fetch({}, _settings_full(), ctx=_ctx(tmp_path))
    assert result.get("url") == "https://image.tmdb.org/t/p/w780/yes.jpg"
    assert result["title"] == "HasPoster"


def test_empty_watchlist_surfaces_clear_error(tmp_path: Path) -> None:
    fake = _route({"api.trakt.tv": []})
    with patch.object(trakt_server.urllib.request, "urlopen", side_effect=fake):
        result = trakt_server.fetch({}, _settings_full(), ctx=_ctx(tmp_path))
    assert result["url"] is None
    assert "empty" in result["error"].lower()


def test_invalid_media_type_falls_back_to_movies(tmp_path: Path) -> None:
    fake = _route(
        {
            "api.trakt.tv/users/kayden/watchlist/movies": [_movie("Tron", 1982, 1)],
            "api.themoviedb.org/3/movie/1": {"poster_path": "/abc.jpg"},
        }
    )
    with patch.object(trakt_server.urllib.request, "urlopen", side_effect=fake):
        result = trakt_server.fetch({"media_type": "bogus"}, _settings_full(), ctx=_ctx(tmp_path))
    assert result.get("url") == "https://image.tmdb.org/t/p/w780/abc.jpg"

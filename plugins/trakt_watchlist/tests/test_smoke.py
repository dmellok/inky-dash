"""Smoke test for the trakt_watchlist widget.

Verifies the cell paints + signals data-rendered=true at each size,
even when Trakt/TMDB aren't configured (the widget should render its
own empty/error state, not crash through to the composer error wrap).
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page


@pytest.mark.parametrize("size", ["md", "lg"])
def test_trakt_watchlist_renders(page: Page, live_server_url: str, size: str) -> None:
    page.goto(f"{live_server_url}/_test/render?plugin=trakt_watchlist&size={size}")
    page.wait_for_selector("[data-rendered=true]", timeout=10000)
    assert page.locator(".cell.error").count() == 0

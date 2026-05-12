"""Smoke test for the clock plugin: renders without errors at every supported size.

Pattern reused by every bundled plugin; see the wiki tutorial → "Testing".
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page


@pytest.mark.parametrize("size", ["xs", "sm", "md", "lg"])
def test_clock_renders(page: Page, live_server_url: str, size: str) -> None:
    page.goto(f"{live_server_url}/_test/render?plugin=clock&size={size}")
    page.wait_for_selector("[data-rendered=true]", timeout=5000)
    assert page.locator(".cell.error").count() == 0

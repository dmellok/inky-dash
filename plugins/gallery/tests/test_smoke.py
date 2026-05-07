from __future__ import annotations

import pytest
from playwright.sync_api import Page


@pytest.mark.parametrize("size", ["md", "lg"])
def test_gallery_renders(page: Page, live_server_url: str, size: str) -> None:
    """Gallery renders the empty-state placeholder if no images are present;
    that's still a successful render."""
    page.goto(f"{live_server_url}/_test/render?plugin=gallery&size={size}")
    page.wait_for_selector("[data-rendered=true]", timeout=10000)
    assert page.locator(".cell.error").count() == 0

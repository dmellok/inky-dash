from __future__ import annotations

import pytest
from playwright.sync_api import Page


@pytest.mark.parametrize("size", ["sm", "md", "lg"])
def test_hn_renders(page: Page, live_server_url: str, size: str) -> None:
    page.goto(f"{live_server_url}/_test/render?plugin=hn&size={size}")
    page.wait_for_selector("[data-rendered=true]", timeout=20000)
    assert page.locator(".cell.error").count() == 0

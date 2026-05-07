from __future__ import annotations

import pytest
from playwright.sync_api import Page


@pytest.mark.parametrize("size", ["xs", "sm", "md", "lg"])
def test_todo_renders(page: Page, live_server_url: str, size: str) -> None:
    page.goto(f"{live_server_url}/_test/render?plugin=todo&size={size}")
    page.wait_for_selector("[data-rendered=true]", timeout=10000)
    assert page.locator(".cell.error").count() == 0

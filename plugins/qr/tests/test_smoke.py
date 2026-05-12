"""Smoke test for the QR widget — renders at md + lg, asserts no error."""

from __future__ import annotations

import pytest
from playwright.sync_api import Page


@pytest.mark.parametrize("size", ["md", "lg"])
def test_qr_renders(page: Page, live_server_url: str, size: str) -> None:
    page.goto(f"{live_server_url}/_test/render?plugin=qr&size={size}")
    page.wait_for_selector("[data-rendered=true]", timeout=10000)
    assert page.locator(".cell.error").count() == 0

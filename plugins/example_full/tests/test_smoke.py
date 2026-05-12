"""Smoke test for the full example widget.

Renders the widget at each of the four breakpoints and asserts the cell
came out with ``data-rendered=true``. Mirrors the smoke tests every
shipped widget keeps under ``plugins/<id>/tests/`` — copy-paste this
file when you're starting a new widget and adjust the plugin id.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page


@pytest.mark.parametrize("size", ["xs", "sm", "md", "lg"])
def test_renders_at_every_size(page: Page, live_server_url: str, size: str) -> None:
    page.goto(f"{live_server_url}/_test/render?plugin=example_full&size={size}")
    page.wait_for_selector("[data-rendered=true]", timeout=10000)
    assert page.locator(".cell.error").count() == 0

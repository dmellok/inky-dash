"""End-to-end browser tests for the admin UI bundle.

These exercise the actual built JS — they fail loudly if static/dist/* is
missing or the Lit components don't mount. They run against the live_server
fixture from the root conftest.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

ROOT = Path(__file__).resolve().parent.parent

requires_built_bundle = pytest.mark.skipif(
    not (ROOT / "static" / "dist" / "editor.js").exists(),
    reason="run `npm run build` (or `bun run build`) first",
)


@requires_built_bundle
def test_components_page_renders_design_system(
    page: Page, live_server_url: str
) -> None:
    page.goto(f"{live_server_url}/_components")
    expect(page.locator("components-demo")).to_be_visible()
    page.wait_for_function(
        "() => { const d = document.querySelector('components-demo'); "
        "return d && d.shadowRoot && d.shadowRoot.querySelector('id-button'); }"
    )


@requires_built_bundle
def test_editor_loads_demo_page(page: Page, live_server_url: str) -> None:
    page.goto(f"{live_server_url}/editor/_demo")
    expect(page.locator("id-editor")).to_be_visible()
    page.wait_for_function(
        "() => { const e = document.querySelector('id-editor'); "
        "return e && e.shadowRoot && e.shadowRoot.querySelector('id-card'); }"
    )

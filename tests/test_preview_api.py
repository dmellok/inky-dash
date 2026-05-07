"""End-to-end tests for the preview API.

Hits the live server (so Playwright inside the request handler can call back
to the same server). Slow — each test launches Chromium once.
"""

from __future__ import annotations

import io

import pytest
import requests
from PIL import Image

from app.quantizer import SPECTRA_6_PALETTE


@pytest.mark.slow
def test_raw_png_endpoint(live_server_url: str) -> None:
    response = requests.get(f"{live_server_url}/api/pages/_demo/raw.png", timeout=30)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    img = Image.open(io.BytesIO(response.content))
    assert img.size == (1600, 1200)


@pytest.mark.slow
def test_preview_png_uses_palette_colours_only(live_server_url: str) -> None:
    response = requests.get(
        f"{live_server_url}/api/pages/_demo/preview.png?dither=none",
        timeout=30,
    )
    assert response.status_code == 200
    img = Image.open(io.BytesIO(response.content)).convert("RGB")
    # Sample a small grid of pixels — full-image scan would be slow.
    sample_xy = [(x, y) for x in range(0, 1600, 200) for y in range(0, 1200, 200)]
    palette = set(SPECTRA_6_PALETTE)
    for x, y in sample_xy:
        pixel = img.getpixel((x, y))
        assert pixel in palette, f"pixel at ({x},{y}) = {pixel} is off-palette"


@pytest.mark.slow
def test_preview_rejects_unknown_dither_mode(live_server_url: str) -> None:
    response = requests.get(
        f"{live_server_url}/api/pages/_demo/preview.png?dither=fake",
        timeout=10,
    )
    assert response.status_code == 400
    assert "invalid dither" in response.json()["error"]


@pytest.mark.slow
def test_preview_404s_on_unknown_page(live_server_url: str) -> None:
    response = requests.get(
        f"{live_server_url}/api/pages/nope/preview.png",
        timeout=10,
    )
    assert response.status_code == 404

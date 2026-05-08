from __future__ import annotations

import io

import pytest
from flask.testing import FlaskClient
from PIL import Image

from app import push as push_module

from ._helpers import FakeBridge

FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture(autouse=True)
def _stub_render(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(push_module, "render_to_png", lambda req: FAKE_PNG)
    monkeypatch.setattr(
        push_module, "quantize_to_png", lambda src, *, dither: FAKE_PNG + dither.encode()
    )


def _real_image_bytes() -> bytes:
    img = Image.new("RGB", (8, 8), color="red")
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def test_send_page_route(client: FlaskClient, fake_bridge: FakeBridge) -> None:
    res = client.post("/api/send/page", json={"page_id": "_demo"})
    assert res.status_code == 200
    body = res.get_json()
    assert body["status"] == "sent"
    assert len(fake_bridge.published) == 1


def test_send_page_missing_page_id(client: FlaskClient) -> None:
    res = client.post("/api/send/page", json={})
    assert res.status_code == 400


def test_send_page_unknown_page(client: FlaskClient) -> None:
    res = client.post("/api/send/page", json={"page_id": "ghost"})
    assert res.status_code == 404


def test_send_page_invalid_dither(client: FlaskClient) -> None:
    res = client.post("/api/send/page", json={"page_id": "_demo", "dither": "ugly"})
    assert res.status_code == 400


def test_send_url_validates_scheme(client: FlaskClient) -> None:
    res = client.post("/api/send/url", json={"url": "ftp://example.com/x.png"})
    assert res.status_code == 400


def test_send_file(client: FlaskClient, fake_bridge: FakeBridge) -> None:
    img_bytes = _real_image_bytes()
    res = client.post(
        "/api/send/file",
        data={"file": (io.BytesIO(img_bytes), "test.png"), "dither": "none"},
        content_type="multipart/form-data",
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["status"] == "sent"
    assert body["url"].endswith(".png")
    assert len(fake_bridge.published) == 1


def test_send_file_no_part(client: FlaskClient) -> None:
    res = client.post("/api/send/file", data={"dither": "none"})
    assert res.status_code == 400


def test_send_webpage_validates_scheme(client: FlaskClient) -> None:
    res = client.post("/api/send/webpage", json={"url": "javascript:alert(1)"})
    assert res.status_code == 400


def _asymmetric_png() -> bytes:
    img = Image.new("RGB", (40, 10), color="blue")
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def test_preview_file_returns_input_dims_unchanged(client: FlaskClient) -> None:
    """Preview shows the dashboard upright (composition orientation). The
    pre-publish rotation is applied only when actually pushing to the panel."""
    res = client.post(
        "/api/send/preview/file",
        data={"file": (io.BytesIO(_asymmetric_png()), "test.png"), "dither": "none"},
        content_type="multipart/form-data",
    )
    assert res.status_code == 200
    img = Image.open(io.BytesIO(res.data))
    assert img.size == (40, 10)


def test_preview_file_portrait_does_not_rotate(client: FlaskClient) -> None:
    """Even in portrait mode the preview is upright — only the push pipeline
    rotates bytes for the panel's landscape-native pixel grid."""
    client.put("/api/app/settings", json={"panel": {"orientation": "portrait"}})
    res = client.post(
        "/api/send/preview/file",
        data={"file": (io.BytesIO(_asymmetric_png()), "test.png"), "dither": "none"},
        content_type="multipart/form-data",
    )
    assert res.status_code == 200
    img = Image.open(io.BytesIO(res.data))
    assert img.size == (40, 10)

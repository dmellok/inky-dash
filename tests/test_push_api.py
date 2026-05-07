"""HTTP-level tests for the push API. Uses test_client + monkeypatched render.

The Flask `app` fixture (in tests/conftest.py) injects a FakeBridge so tests
don't need a real broker; we monkeypatch render_to_png/quantize_to_png so
they don't need Chromium.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from flask.testing import FlaskClient

from app import push as push_module
from app.mqtt_bridge import ListenerStatus

from ._helpers import FakeBridge

FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


@pytest.fixture(autouse=True)
def _stub_render(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(push_module, "render_to_png", lambda req: FAKE_PNG)
    monkeypatch.setattr(
        push_module, "quantize_to_png", lambda src, *, dither: FAKE_PNG + dither.encode()
    )


def test_push_returns_sent_with_digest(client: FlaskClient, fake_bridge: FakeBridge) -> None:
    response = client.post("/api/pages/_demo/push")
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "sent"
    assert body["digest"] is not None
    assert body["url"].endswith(f"/renders/{body['digest']}.png")
    assert len(fake_bridge.published) == 1


def test_push_artifact_served_via_renders_route(client: FlaskClient, app: object) -> None:
    push_response = client.post("/api/pages/_demo/push")
    digest = push_response.get_json()["digest"]
    file_response = client.get(f"/renders/{digest}.png")
    assert file_response.status_code == 200
    assert file_response.headers["content-type"] == "image/png"


def test_push_unknown_page_returns_404(client: FlaskClient) -> None:
    response = client.post("/api/pages/missing/push")
    assert response.status_code == 404


def test_push_invalid_options_returns_400(client: FlaskClient) -> None:
    response = client.post("/api/pages/_demo/push", json={"rotate": 45})
    assert response.status_code == 400
    assert "rotate" in response.get_json()["error"]


def test_push_invalid_dither_returns_400(client: FlaskClient) -> None:
    response = client.post("/api/pages/_demo/push", json={"dither": "ugly"})
    assert response.status_code == 400


def test_history_endpoint_returns_recorded_pushes(client: FlaskClient) -> None:
    client.post("/api/pages/_demo/push")
    response = client.get("/api/history")
    body = response.get_json()
    assert response.status_code == 200
    assert isinstance(body, list)
    assert any(record["page_id"] == "_demo" for record in body)


def test_listener_status_unknown_when_bridge_has_no_status(
    client: FlaskClient,
) -> None:
    response = client.get("/api/listener/status")
    assert response.status_code == 200
    assert response.get_json()["state"] == "unknown"


def test_listener_status_passes_through_when_bridge_has_status(
    client: FlaskClient, fake_bridge: FakeBridge
) -> None:
    fake_bridge.set_status(
        ListenerStatus(
            state="idle",
            raw={"state": "idle", "last_result": "ok"},
            received_at=datetime.now(UTC),
        )
    )
    body = client.get("/api/listener/status").get_json()
    assert body["state"] == "idle"
    assert body["raw"]["last_result"] == "ok"


def test_renders_route_rejects_malformed_digest(client: FlaskClient) -> None:
    assert client.get("/renders/not-hex.png").status_code == 404


def test_renders_route_404s_for_missing_digest(client: FlaskClient, tmp_path: Path) -> None:
    # 16 hex chars but no file exists for it
    assert client.get("/renders/0123456789abcdef.png").status_code == 404

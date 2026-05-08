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


def test_history_includes_published_payload_and_topic(client: FlaskClient) -> None:
    """The MQTT payload + topic that went out are stored on each push so the
    user can debug 'why isn't the panel updating?' from the history view."""
    client.post("/api/pages/_demo/push")
    body = client.get("/api/history").get_json()
    record = next(r for r in body if r["page_id"] == "_demo")
    assert record["topic"] == "inky/update"
    payload = record["payload"]
    assert "url" in payload
    assert payload["url"].endswith(".png")
    assert payload["rotate"] == 0
    assert payload["scale"] == "fit"


def test_history_records_payload_even_when_publish_fails(
    client: FlaskClient, fake_bridge: FakeBridge
) -> None:
    """If MQTT publish raises, we still want the attempted payload in history
    so the user can see what we tried to send."""
    fake_bridge.raise_on_publish = RuntimeError("broker unreachable")
    client.post("/api/pages/_demo/push")
    body = client.get("/api/history").get_json()
    record = body[0]
    assert record["status"] == "failed"
    assert "broker unreachable" in (record["error"] or "")
    assert record["topic"] == "inky/update"
    assert "url" in record["payload"]


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


def test_listener_log_returns_recent_status_messages(
    client: FlaskClient, fake_bridge: FakeBridge
) -> None:
    """/api/listener/log exposes the ring buffer of inky/status messages so
    the user can see what the panel reported back after each push."""
    assert client.get("/api/listener/log").get_json() == []
    fake_bridge.set_status(
        ListenerStatus(
            state="rendering",
            raw={"state": "rendering", "digest": "abc"},
            received_at=datetime.now(UTC),
        )
    )
    fake_bridge.set_status(
        ListenerStatus(
            state="idle",
            raw={"state": "idle", "last_result": "ok"},
            received_at=datetime.now(UTC),
        )
    )
    body = client.get("/api/listener/log").get_json()
    # Newest-first ordering.
    assert [s["state"] for s in body] == ["idle", "rendering"]
    assert body[0]["raw"]["last_result"] == "ok"


def test_renders_route_rejects_malformed_digest(client: FlaskClient) -> None:
    assert client.get("/renders/not-hex.png").status_code == 404


def test_renders_route_404s_for_missing_digest(client: FlaskClient, tmp_path: Path) -> None:
    # 16 hex chars but no file exists for it
    assert client.get("/renders/0123456789abcdef.png").status_code == 404


# ---- /api/pages/push-inline -------------------------------------------------

DRAFT_PAGE = {
    "id": "ignored-by-server",
    "name": "Draft",
    "panel": {"w": 800, "h": 480},
    "cells": [
        {
            "id": "c1",
            "x": 0,
            "y": 0,
            "w": 800,
            "h": 480,
            "plugin": "clock",
            "options": {},
        }
    ],
}


def test_push_inline_sends_without_persisting_page(
    client: FlaskClient, fake_bridge: FakeBridge
) -> None:
    res = client.post("/api/pages/push-inline", json={"page": DRAFT_PAGE})
    assert res.status_code == 200
    body = res.get_json()
    assert body["status"] == "sent"
    assert body["digest"]
    assert len(fake_bridge.published) == 1
    # The transient id is NOT visible in the page list afterwards.
    listing = client.get("/api/pages").get_json()
    assert all(not p["id"].startswith("_preview_") for p in listing)
    # Nor was DRAFT_PAGE.id ("ignored-by-server") created — the server overrides it.
    assert all(p["id"] != "ignored-by-server" for p in listing)


def test_push_inline_does_not_overwrite_an_existing_page(
    client: FlaskClient, fake_bridge: FakeBridge
) -> None:
    """If a page with the inline id already exists, sending must leave it untouched."""
    # Seed a page with id `_demo` (already exists from the fixture). Mutate the inline
    # draft to share that id and push — the saved page must not change.
    before = client.get("/api/pages/_demo").get_json()
    draft = {**DRAFT_PAGE, "id": "_demo", "name": "MUTATED"}
    res = client.post("/api/pages/push-inline", json={"page": draft})
    assert res.status_code == 200
    after = client.get("/api/pages/_demo").get_json()
    assert after == before


def test_push_inline_validation_error(client: FlaskClient) -> None:
    bad = {**DRAFT_PAGE, "panel": {"w": 0, "h": 0}}  # w must be >= 1
    res = client.post("/api/pages/push-inline", json={"page": bad})
    assert res.status_code == 400
    assert res.get_json()["error"] == "validation"


def test_push_inline_requires_page(client: FlaskClient) -> None:
    res = client.post("/api/pages/push-inline", json={})
    assert res.status_code == 400


def test_push_inline_invalid_dither(client: FlaskClient) -> None:
    res = client.post(
        "/api/pages/push-inline", json={"page": DRAFT_PAGE, "dither": "ugly"}
    )
    assert res.status_code == 400


def test_push_inline_records_history(client: FlaskClient) -> None:
    client.post("/api/pages/push-inline", json={"page": DRAFT_PAGE})
    body = client.get("/api/history").get_json()
    # The transient id is what's recorded — surfaces clearly as a preview.
    assert any(r["page_id"].startswith("_preview_") for r in body)

from __future__ import annotations

from datetime import UTC, datetime

from flask.testing import FlaskClient


def _interval_body(id_: str = "morning", **overrides) -> dict:
    base = {
        "id": id_,
        "name": id_.title(),
        "page_id": "_demo",
        "type": "interval",
        "interval_minutes": 60,
    }
    base.update(overrides)
    return base


def test_empty_listing(client: FlaskClient) -> None:
    body = client.get("/api/schedules").get_json()
    assert body == []


def test_put_creates_schedule(client: FlaskClient) -> None:
    res = client.put("/api/schedules/morning", json=_interval_body())
    assert res.status_code == 200
    listed = client.get("/api/schedules").get_json()
    assert [s["id"] for s in listed] == ["morning"]


def test_put_id_mismatch_400(client: FlaskClient) -> None:
    res = client.put("/api/schedules/wrong", json=_interval_body())
    assert res.status_code == 400


def test_put_invalid_returns_400_with_details(client: FlaskClient) -> None:
    bad = _interval_body()
    bad["interval_minutes"] = 0
    res = client.put("/api/schedules/morning", json=bad)
    assert res.status_code == 400
    body = res.get_json()
    assert body["error"] == "validation"
    assert "details" in body


def test_get_unknown_404(client: FlaskClient) -> None:
    assert client.get("/api/schedules/never").status_code == 404


def test_delete(client: FlaskClient) -> None:
    client.put("/api/schedules/x", json=_interval_body("x"))
    assert client.delete("/api/schedules/x").status_code == 204
    assert client.delete("/api/schedules/x").status_code == 404


def test_oneshot_round_trip(client: FlaskClient) -> None:
    fires = datetime(2026, 12, 25, 9, 0, tzinfo=UTC).isoformat()
    body = {
        "id": "xmas",
        "name": "Christmas",
        "page_id": "_demo",
        "type": "oneshot",
        "fires_at": fires,
    }
    res = client.put("/api/schedules/xmas", json=body)
    assert res.status_code == 200
    saved = client.get("/api/schedules/xmas").get_json()
    assert saved["type"] == "oneshot"


def test_schedules_page_renders_shell(client: FlaskClient) -> None:
    res = client.get("/schedules")
    assert res.status_code == 200
    assert b"dist/schedules.js" in res.data


def test_send_page_renders_shell(client: FlaskClient) -> None:
    res = client.get("/send")
    assert res.status_code == 200
    assert b"dist/send.js" in res.data

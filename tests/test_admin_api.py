from __future__ import annotations

from flask.testing import FlaskClient

VALID_PAGE = {
    "id": "test_page",
    "name": "Test page",
    "panel": {"w": 1600, "h": 1200},
    "cells": [
        {
            "id": "c1",
            "x": 0,
            "y": 0,
            "w": 800,
            "h": 600,
            "plugin": "clock",
            "options": {},
        }
    ],
}


def test_list_pages_includes_seeded_demo(client: FlaskClient) -> None:
    response = client.get("/api/pages")
    assert response.status_code == 200
    ids = [p["id"] for p in response.get_json()]
    assert "_demo" in ids


def test_get_unknown_page_404s(client: FlaskClient) -> None:
    assert client.get("/api/pages/nope").status_code == 404


def test_put_creates_page(client: FlaskClient) -> None:
    response = client.put("/api/pages/test_page", json=VALID_PAGE)
    assert response.status_code == 200
    assert client.get("/api/pages/test_page").status_code == 200


def test_put_id_mismatch_400(client: FlaskClient) -> None:
    response = client.put("/api/pages/wrong_id", json=VALID_PAGE)
    assert response.status_code == 400


def test_put_validation_error_returns_400(client: FlaskClient) -> None:
    bad = {**VALID_PAGE, "name": ""}
    response = client.put("/api/pages/test_page", json=bad)
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "validation"


def test_delete_page(client: FlaskClient) -> None:
    client.put("/api/pages/test_page", json=VALID_PAGE)
    assert client.delete("/api/pages/test_page").status_code == 204
    assert client.delete("/api/pages/test_page").status_code == 404


def test_widgets_endpoint_includes_clock(client: FlaskClient) -> None:
    response = client.get("/api/widgets")
    assert response.status_code == 200
    ids = [w["id"] for w in response.get_json()]
    assert "clock" in ids


def test_editor_route_renders_shell(client: FlaskClient) -> None:
    response = client.get("/editor/_demo")
    assert response.status_code == 200
    assert b'data-page-id="_demo"' in response.data
    assert b"dist/editor.js" in response.data


def test_components_route_renders_shell(client: FlaskClient) -> None:
    response = client.get("/_components")
    assert response.status_code == 200
    assert b"dist/components-demo.js" in response.data

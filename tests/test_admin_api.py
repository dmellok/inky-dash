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


def test_editor_index_renders_dashboards_list(client: FlaskClient) -> None:
    """The /editor route is the dashboards list, not the bare editor shell."""
    response = client.get("/editor")
    assert response.status_code == 200
    assert b"dist/dashboards.js" in response.data
    assert b"dist/editor.js" not in response.data


def test_create_page_with_just_name(client: FlaskClient) -> None:
    res = client.post("/api/pages", json={"name": "Kitchen wall"})
    assert res.status_code == 201
    body = res.get_json()
    assert body["id"] == "kitchen-wall"
    assert body["name"] == "Kitchen wall"
    # The new page is persisted and listable.
    listing = client.get("/api/pages").get_json()
    assert any(p["id"] == "kitchen-wall" for p in listing)
    # It has a single full-bleed cell with the clock plugin.
    assert len(body["cells"]) == 1
    cell = body["cells"][0]
    assert cell["plugin"] == "clock"
    assert cell["w"] == body["panel"]["w"]
    assert cell["h"] == body["panel"]["h"]


def test_create_page_uses_panel_app_settings_for_dimensions(client: FlaskClient) -> None:
    """When app.panel is the 7.3" portrait, new pages should be 480×800."""
    client.put(
        "/api/app/settings",
        json={"panel": {"model": "impression_7_3", "orientation": "portrait"}},
    )
    res = client.post("/api/pages", json={"name": "Tablet"})
    assert res.status_code == 201
    body = res.get_json()
    # Native 800×480; portrait swaps → 480×800.
    assert body["panel"] == {"w": 480, "h": 800}


def test_create_page_landscape_native_dimensions(client: FlaskClient) -> None:
    client.put(
        "/api/app/settings",
        json={"panel": {"model": "impression_7_3", "orientation": "landscape"}},
    )
    res = client.post("/api/pages", json={"name": "Wide"})
    body = res.get_json()
    assert body["panel"] == {"w": 800, "h": 480}


def test_create_page_collision_appends_suffix(client: FlaskClient) -> None:
    client.post("/api/pages", json={"name": "Status"})
    res = client.post("/api/pages", json={"name": "Status"})
    assert res.status_code == 201
    assert res.get_json()["id"] == "status-2"
    res = client.post("/api/pages", json={"name": "Status"})
    assert res.get_json()["id"] == "status-3"


def test_create_page_explicit_id_collision_409s(client: FlaskClient) -> None:
    client.post("/api/pages", json={"name": "First", "id": "shared"})
    res = client.post("/api/pages", json={"name": "Second", "id": "shared"})
    assert res.status_code == 409


def test_create_page_rejects_empty_name(client: FlaskClient) -> None:
    assert client.post("/api/pages", json={"name": "   "}).status_code == 400
    assert client.post("/api/pages", json={}).status_code == 400


def test_create_page_rejects_unslugifiable_name(client: FlaskClient) -> None:
    """A name that produces no slug chars (only punctuation)."""
    res = client.post("/api/pages", json={"name": "!!!"})
    assert res.status_code == 400


def test_create_page_rejects_invalid_explicit_id(client: FlaskClient) -> None:
    res = client.post("/api/pages", json={"name": "Test", "id": "Bad ID!"})
    assert res.status_code == 400


# ---- preview cache (live editor render) -------------------------------------

PREVIEW_DRAFT = {
    "id": "_demo",
    "name": "DRAFTED",
    "panel": {"w": 800, "h": 600},
    "cells": [{"id": "c1", "x": 0, "y": 0, "w": 800, "h": 600, "plugin": "clock", "options": {}}],
}


def test_stage_preview_then_compose_uses_draft(client: FlaskClient, app: object) -> None:
    """Composer should serve the staged preview before falling back to disk."""
    res = client.put("/api/pages/_demo/preview", json=PREVIEW_DRAFT)
    assert res.status_code == 204
    cache = app.config["PREVIEW_CACHE"]  # type: ignore[attr-defined]
    assert "_demo" in cache
    # Compose endpoint reflects the draft, not the saved demo page.
    html = client.get("/compose/_demo").data
    # The drafted page is 800x600; the saved demo is 1600x1200.
    assert b"width: 800px" in html


def test_stage_preview_validation_error(client: FlaskClient) -> None:
    bad = {**PREVIEW_DRAFT, "panel": {"w": 0, "h": 0}}
    res = client.put("/api/pages/_demo/preview", json=bad)
    assert res.status_code == 400


def test_clear_preview(client: FlaskClient, app: object) -> None:
    client.put("/api/pages/_demo/preview", json=PREVIEW_DRAFT)
    res = client.delete("/api/pages/_demo/preview")
    assert res.status_code == 204
    assert "_demo" not in app.config["PREVIEW_CACHE"]  # type: ignore[attr-defined]


def test_save_clears_preview_cache(client: FlaskClient, app: object) -> None:
    """Saving a page should invalidate any in-flight preview draft for it."""
    client.put("/api/pages/_demo/preview", json=PREVIEW_DRAFT)
    saved = client.get("/api/pages/_demo").get_json()
    client.put("/api/pages/_demo", json=saved)
    assert "_demo" not in app.config["PREVIEW_CACHE"]  # type: ignore[attr-defined]


# ---- plugin admin-pages icon ------------------------------------------------


def test_admin_pages_endpoint_includes_icon(client: FlaskClient) -> None:
    body = client.get("/api/plugins/admin-pages").get_json()
    by_id = {p["id"]: p for p in body}
    assert by_id["gallery"]["icon"] == "ph-images"
    assert by_id["todo"]["icon"] == "ph-list-checks"

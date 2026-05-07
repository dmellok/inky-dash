from __future__ import annotations

from flask.testing import FlaskClient

from app import VERSION


def test_index_responds(client: FlaskClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert VERSION in response.get_data(as_text=True)


def test_healthz(client: FlaskClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["version"] == VERSION
    assert "plugins" in body


def test_compose_demo_page(client: FlaskClient) -> None:
    response = client.get("/compose/_demo")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'data-plugin="clock"' in html


def test_compose_unknown_page_404s(client: FlaskClient) -> None:
    assert client.get("/compose/does-not-exist").status_code == 404


def test_test_render_route_available_in_testing(client: FlaskClient) -> None:
    response = client.get("/_test/render?plugin=clock&size=md")
    assert response.status_code == 200


def test_test_render_rejects_unknown_size(client: FlaskClient) -> None:
    assert client.get("/_test/render?plugin=clock&size=huge").status_code == 400

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
    assert response.get_json() == {"status": "ok", "version": VERSION}

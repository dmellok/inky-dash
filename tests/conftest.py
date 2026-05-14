from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from app.auth import SESSION_KEY_AUTHED, hash_password

from ._helpers import FakeBridge

TEST_PASSWORD = "test-password-1234"


@pytest.fixture
def fake_bridge() -> FakeBridge:
    return FakeBridge()


@pytest.fixture
def app(tmp_path: Path, fake_bridge: FakeBridge) -> Flask:
    # start_scheduler=False keeps the daemon thread out of tests so they
    # remain deterministic (no surprise pushes mid-assertion).
    app = create_app(data_root=tmp_path / "data", bridge=fake_bridge, start_scheduler=False)
    app.config["TESTING"] = True
    # Seed a known password so the auth gate doesn't bounce every test to
    # /setup. The default ``client`` fixture below also flips the session
    # ``authed`` bit so existing tests don't have to think about login.
    store = app.config["APP_SETTINGS_STORE"]
    settings = store.load()
    settings.auth.password_hash = hash_password(TEST_PASSWORD)
    store.save(settings)
    return app


@pytest.fixture
def client(app: Flask) -> Iterator[FlaskClient]:
    """Authenticated test client — the default. Use ``unauth_client``
    when you need to exercise the gate itself."""
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess[SESSION_KEY_AUTHED] = True
        yield client


@pytest.fixture
def unauth_client(app: Flask) -> Iterator[FlaskClient]:
    """Test client with a fresh session (no auth). For testing the
    redirect / 401 behaviour of the auth gate."""
    with app.test_client() as client:
        yield client

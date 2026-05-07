from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app

from ._helpers import FakeBridge


@pytest.fixture
def fake_bridge() -> FakeBridge:
    return FakeBridge()


@pytest.fixture
def app(tmp_path: Path, fake_bridge: FakeBridge) -> Flask:
    # start_scheduler=False keeps the daemon thread out of tests so they
    # remain deterministic (no surprise pushes mid-assertion).
    app = create_app(data_root=tmp_path / "data", bridge=fake_bridge, start_scheduler=False)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app: Flask) -> Iterator[FlaskClient]:
    with app.test_client() as client:
        yield client

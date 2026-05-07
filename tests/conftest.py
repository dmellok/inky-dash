from __future__ import annotations

from collections.abc import Iterator

import pytest
from flask.testing import FlaskClient

from app import create_app


@pytest.fixture
def client() -> Iterator[FlaskClient]:
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

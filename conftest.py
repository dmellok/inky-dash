"""Root-level conftest.

Lives at the repo root so fixtures here are visible to both ``tests/`` and
``plugins/<id>/tests/``. Per-area fixtures stay inside their own directory's
conftest.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator

import pytest
from werkzeug.serving import BaseWSGIServer, make_server

from app import create_app


@pytest.fixture(scope="session")
def live_server_url(tmp_path_factory: pytest.TempPathFactory) -> Iterator[str]:
    """Run the real Flask app on an ephemeral localhost port for browser tests."""
    data_root = tmp_path_factory.mktemp("live-data")
    app = create_app(data_root=data_root)
    app.config["TESTING"] = True
    server: BaseWSGIServer = make_server("127.0.0.1", 0, app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)

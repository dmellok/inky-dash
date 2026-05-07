"""Regression: cell options + plugin data flow through Jinja's ``tojson`` filter
into single-quoted HTML attributes. Special characters (``'``, ``"``, ``<``,
``>``, ``&``) must be escaped or the attribute breaks on the client.

Jinja's tojson handles this by Unicode-escaping the unsafe set; the test
confirms the round-trip rather than the specific encoding.
"""

from __future__ import annotations

import json
import re

from flask.testing import FlaskClient


def _extract_attr(html: str, attr: str) -> str | None:
    """Pull a single-quoted attribute value out of the HTML."""
    match = re.search(rf"\b{attr}='([^']*)'", html)
    return match.group(1) if match else None


def test_special_chars_in_cell_options_round_trip(client: FlaskClient) -> None:
    nasty = 'Bob\'s <script>"big" & bold</script>'
    page = {
        "id": "encoding_test",
        "name": "encoding test",
        "panel": {"w": 400, "h": 300},
        "cells": [
            {
                "id": "c",
                "x": 0,
                "y": 0,
                "w": 400,
                "h": 300,
                "plugin": "clock",
                "options": {"label": nasty, "format": "24h"},
            }
        ],
    }
    save = client.put("/api/pages/encoding_test", json=page)
    assert save.status_code == 200

    response = client.get("/compose/encoding_test")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    # No literal apostrophe leaks into the attribute value (would break parsing).
    assert "Bob's" not in html, "apostrophe wasn't escaped"

    # Round-trip the attribute as JSON to prove it parses cleanly.
    raw = _extract_attr(html, "data-options")
    assert raw is not None, "data-options attribute missing"
    parsed = json.loads(raw)
    assert parsed["label"] == nasty


def test_compose_contains_no_unescaped_script_tags_from_data(client: FlaskClient) -> None:
    """A plugin whose data contains a literal <script> tag must not produce
    an executable script in the page (defence-in-depth even if Jinja's
    autoescape is doing its job)."""
    page = {
        "id": "xss_check",
        "name": "xss check",
        "panel": {"w": 200, "h": 200},
        "cells": [
            {
                "id": "c",
                "x": 0,
                "y": 0,
                "w": 200,
                "h": 200,
                "plugin": "clock",
                "options": {"format": "<script>alert(1)</script>"},
            }
        ],
    }
    client.put("/api/pages/xss_check", json=page)
    html = client.get("/compose/xss_check").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in html

"""Pydantic ↔ JSON Schema parity tests.

The JSON Schema is the documented source of truth (v4-brief §10). Pydantic
models in app/page_model.py are hand-aligned. These tests assert both accept
the same examples and reject the same bad data, so drift is caught on PR.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema
import pytest
from pydantic import ValidationError

from app.state import Page

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "schema" / "page.schema.json").read_text())


VALID_PAGE: dict[str, Any] = {
    "id": "demo",
    "name": "Demo",
    "panel": {"w": 1600, "h": 1200},
    "cells": [
        {
            "id": "cell-1",
            "x": 0,
            "y": 0,
            "w": 800,
            "h": 600,
            "plugin": "clock",
            "options": {"format": "24h"},
        }
    ],
}


def test_valid_page_accepted_by_both() -> None:
    jsonschema.validate(VALID_PAGE, SCHEMA)
    page = Page.model_validate(VALID_PAGE)
    assert page.id == "demo"
    assert page.cells[0].plugin == "clock"


def test_default_theme_and_font() -> None:
    page = Page.model_validate(VALID_PAGE)
    assert page.theme == "default"
    assert page.font == "default"


def test_round_trip_dump_then_load() -> None:
    page = Page.model_validate(VALID_PAGE)
    dumped = page.model_dump(mode="json")
    jsonschema.validate(dumped, SCHEMA)
    Page.model_validate(dumped)


@pytest.mark.parametrize(
    "mutation",
    [
        {"id": "BAD-CAPS"},  # uppercase rejected
        {"name": ""},  # empty name
        {"panel": {"w": 0, "h": 1200}},  # zero width
        {"cells": [{"id": "x", "x": -1, "y": 0, "w": 10, "h": 10, "plugin": "clock"}]},
        {"cells": [{"id": "x", "x": 0, "y": 0, "w": 10, "h": 10, "plugin": "Bad-Plugin"}]},
    ],
)
def test_both_validators_reject(mutation: dict[str, Any]) -> None:
    bad = {**VALID_PAGE, **mutation}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, SCHEMA)
    with pytest.raises(ValidationError):
        Page.model_validate(bad)


def test_unknown_top_level_field_rejected_by_both() -> None:
    bad = {**VALID_PAGE, "rogue_field": True}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, SCHEMA)
    with pytest.raises(ValidationError):
        Page.model_validate(bad)

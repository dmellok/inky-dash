"""Pydantic models for the page schema.

The JSON Schema at ``schema/page.schema.json`` is the source of truth (see
v4-brief §10). These models are hand-aligned with it; a test asserts both
accept/reject the same example data so drift is caught.

mypy --strict applies to ``app.state.*`` per v4-brief §6; this module is
re-exported via ``app.state``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_STRICT = ConfigDict(extra="forbid")


class Panel(BaseModel):
    model_config = _STRICT
    w: int = Field(ge=1)
    h: int = Field(ge=1)


class Cell(BaseModel):
    model_config = _STRICT
    id: str = Field(min_length=1)
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    w: int = Field(ge=1)
    h: int = Field(ge=1)
    plugin: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    options: dict[str, Any] = Field(default_factory=dict)
    theme: str | None = None
    font: str | None = None


class Page(BaseModel):
    model_config = _STRICT
    id: str = Field(pattern=r"^[a-z0-9_][a-z0-9_-]*$")
    name: str = Field(min_length=1)
    panel: Panel
    theme: str = "default"
    font: str = "default"
    gap: int = Field(default=0, ge=0, le=200)
    corner_radius: int = Field(default=0, ge=0, le=200)
    cells: list[Cell] = Field(default_factory=list)

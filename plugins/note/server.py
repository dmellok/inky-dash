"""Sticky note — purely client-rendered. Server returns nothing useful;
all the content lives in cell_options.
"""

from __future__ import annotations

from typing import Any


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    return {}

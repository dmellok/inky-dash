"""Generative art widget — no network, no state. All rendering happens
client-side; the server only hands back today's date so the seed stays
stable across cells in the same render."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    return {"date": datetime.now(UTC).date().isoformat()}

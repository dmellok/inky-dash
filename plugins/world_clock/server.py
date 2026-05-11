"""World clock — pure-client widget. Server returns nothing useful; the
client uses Intl.DateTimeFormat + the zones list parsed from cell_options
to render every tick. Refresh happens client-side every minute."""

from __future__ import annotations

from typing import Any


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    return {}

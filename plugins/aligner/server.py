"""Frame aligner widget — no network, no state.

The visual is rendered entirely client-side; the server is here only so the
plugin loader is happy and so we can hand the cell its pixel dimensions
back through the standard fetch contract.
"""

from __future__ import annotations

from typing import Any


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    return {}

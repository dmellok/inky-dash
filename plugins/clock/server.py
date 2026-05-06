"""Clock widget — server-side time at render moment.

The server's wall clock is the ground truth at push time. The client
renders this snapshot for static panels and ticks live in preview/editor
contexts so the editor preview doesn't show a frozen face.
"""
from __future__ import annotations

from datetime import datetime


def fetch(options, settings, *, panel_w, panel_h, preview=False):
    now = datetime.now().astimezone()
    return {
        "iso": now.isoformat(timespec="seconds"),
        # Pre-computed strings save the client a few branches and ensure the
        # rendered output exactly matches the server's locale snapshot.
        "weekday": now.strftime("%A"),
        "date_long": now.strftime("%-d %B %Y"),
    }

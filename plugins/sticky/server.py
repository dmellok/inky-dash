"""Sticky note widget — display-weight text you configure in the cell options.

Pure passthrough: server just relays the text/subtitle/icon to the client.
Lives behind a fetch() so the widget contract stays consistent across
plugins (lets schedulers and previews treat it like any other widget).
"""
from __future__ import annotations


def fetch(options, settings, *, panel_w, panel_h, preview=False):
    return {
        "text": (options.get("text") or "").strip(),
        "subtitle": (options.get("subtitle") or "").strip(),
        "icon": (options.get("icon") or "ph-note").strip(),
        "align": (options.get("align") or "center").strip(),
    }

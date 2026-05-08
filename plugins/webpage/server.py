"""Webpage widget — server-side just validates the URL.

Actual rendering is an <iframe> in the cell; Playwright captures it as
part of the dashboard screenshot. The plugin doesn't fetch the page
itself — that would defeat the purpose of letting the headless browser
handle JS-driven sites. Note: many sites refuse iframe embedding via
X-Frame-Options or Content-Security-Policy; this widget can't bypass
those.
"""

from __future__ import annotations

from typing import Any


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    url = (options.get("url") or "").strip()
    if not url:
        return {"error": "Set a URL in the cell options.", "url": None}
    if not (url.startswith("http://") or url.startswith("https://")):
        return {"error": "URL must start with http:// or https://", "url": None}
    return {"url": url}

"""Gallery — picks an image from data_dir and serves it via a blueprint route."""

from __future__ import annotations

import contextlib
import random
from pathlib import Path
from typing import Any

from flask import Blueprint, abort, current_app, send_from_directory

ALLOWED_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif"})


def _list_images(data_dir: Path) -> list[Path]:
    if not data_dir.exists():
        return []
    return sorted(
        p for p in data_dir.iterdir() if p.is_file() and p.suffix.lower() in ALLOWED_SUFFIXES
    )


def _index_path(data_dir: Path) -> Path:
    return data_dir / ".sequential_index"


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    data_dir = Path(ctx["data_dir"])
    images = _list_images(data_dir)
    if not images:
        return {
            "error": (
                f"No images found. Drop JPG / PNG / WEBP files into {data_dir} and re-render."
            ),
            "url": None,
        }

    mode = options.get("mode", "random")
    if mode == "sequential":
        idx_file = _index_path(data_dir)
        try:
            current = int(idx_file.read_text())
        except (FileNotFoundError, ValueError):
            current = -1
        next_idx = (current + 1) % len(images)
        with contextlib.suppress(OSError):
            idx_file.write_text(str(next_idx))
        chosen = images[next_idx]
    else:
        chosen = random.choice(images)

    return {
        "url": f"/plugins/gallery/images/{chosen.name}",
        "filename": chosen.name,
        "count": len(images),
    }


def blueprint() -> Blueprint:
    bp = Blueprint("gallery_admin", __name__)

    @bp.get("/images/<path:filename>")
    def serve_image(filename: str) -> Any:
        plugin = current_app.config["PLUGIN_REGISTRY"].plugins.get("gallery")
        if plugin is None:
            abort(404)
        return send_from_directory(plugin.data_dir, filename)

    @bp.get("/")
    def index() -> str:
        plugin = current_app.config["PLUGIN_REGISTRY"].plugins["gallery"]
        images = _list_images(plugin.data_dir)
        rows = "\n".join(
            f'<li><img src="/plugins/gallery/images/{p.name}" alt=""><span>{p.name}</span></li>'
            for p in images
        )
        return f"""
        <!doctype html><html><head><meta charset="utf-8"><title>Gallery</title>
        <style>
          body {{ font: 14px/1.5 system-ui, sans-serif; max-width: 720px; margin: 24px auto; padding: 0 16px; }}
          ul {{ list-style: none; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 12px; }}
          li {{ border: 1px solid #c8b89b; border-radius: 6px; overflow: hidden; }}
          li img {{ display: block; width: 100%; aspect-ratio: 4/3; object-fit: cover; }}
          li span {{ display: block; padding: 6px 8px; font-size: 12px; color: #5a4f44; word-break: break-all; }}
          .empty {{ padding: 24px; color: #5a4f44; }}
          a {{ color: #5a4f44; text-decoration: none; font-size: 13px; }}
        </style></head><body>
        <a href="/editor">← back to editor</a>
        <h1 style="font-size:20px;">Gallery — {len(images)} image(s)</h1>
        <p>Drop JPG / PNG / WEBP files into <code>{plugin.data_dir}</code> then refresh.</p>
        {f"<ul>{rows}</ul>" if images else '<p class="empty">No images yet.</p>'}
        </body></html>
        """

    return bp

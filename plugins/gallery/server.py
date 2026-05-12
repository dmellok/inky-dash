"""Gallery — folder-based image rotation.

A "folder" can be either:
  - **Internal** — a subdirectory under ``data/plugins/gallery/`` that we own.
    Images are uploaded via the admin UI's drop zone.
  - **External** — a pointer to any directory on the host (``/Users/me/Pictures/Vacation``,
    a network mount, etc.). The plugin reads + serves the images but never
    writes to that directory; uploads to external folders are rejected.

Folder metadata (display label, type, external path) lives in
``data/plugins/gallery/.folders.json``. Internal folders get a directory on
disk; external folders are entries in this file pointing at an absolute path.

The plugin's ``fetch()`` honours ``options.folder``; ``choices("folders")``
returns the list of available folders so the editor can populate the
dropdown for ``cell_options.folder``.
"""

from __future__ import annotations

import contextlib
import json
import os
import random
import re
import shutil
from pathlib import Path
from typing import Any

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    render_template_string,
    request,
    send_file,
    send_from_directory,
)
from PIL import Image, ImageOps
from werkzeug.utils import secure_filename

ALLOWED_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif"})
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB per file
_FOLDER_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
ROOT_FOLDER_VALUE = "_root"  # encodes the data_dir root
META_FILE = ".folders.json"
THUMB_DIR = ".thumb_cache"
THUMB_SIZE = (320, 240)  # bounding box for thumbnails
ORIENT_CACHE_FILE = ".orientation_cache.json"
SQUARE_TOLERANCE = 0.05  # ±5 % around w==h counts as square


def _data_dir() -> Path:
    return current_app.config["PLUGIN_REGISTRY"].plugins["gallery"].data_dir


# -- Metadata: folder labels + external paths --------------------------------


def _meta_path(data_dir: Path) -> Path:
    return data_dir / META_FILE


def _load_meta(data_dir: Path) -> dict[str, dict[str, Any]]:
    path = _meta_path(data_dir)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_meta(data_dir: Path, meta: dict[str, dict[str, Any]]) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    tmp = _meta_path(data_dir).with_suffix(".json.tmp")
    tmp.write_text(json.dumps(meta, indent=2, sort_keys=True))
    os.replace(tmp, _meta_path(data_dir))


def _folder_path(folder_name: str, data_dir: Path) -> Path | None:
    """Resolve a folder identifier to the directory that holds its images.

    Returns None for invalid names. Returns the external path for external
    folders, or the internal subdirectory otherwise.
    """
    if not folder_name or folder_name == ROOT_FOLDER_VALUE:
        return data_dir
    if not _FOLDER_NAME_RE.match(folder_name):
        return None
    meta = _load_meta(data_dir).get(folder_name, {})
    if meta.get("external_path"):
        try:
            return Path(meta["external_path"]).expanduser().resolve()
        except OSError:
            return None
    return data_dir / folder_name


def _is_external(folder_name: str, data_dir: Path) -> bool:
    if not folder_name or folder_name == ROOT_FOLDER_VALUE:
        return False
    return bool(_load_meta(data_dir).get(folder_name, {}).get("external_path"))


def _list_images(folder: Path | None) -> list[Path]:
    if folder is None or not folder.exists() or not folder.is_dir():
        return []
    try:
        return sorted(
            p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in ALLOWED_SUFFIXES
        )
    except (PermissionError, OSError):
        return []


def _list_internal_folders(data_dir: Path) -> list[str]:
    if not data_dir.exists():
        return []
    return sorted(
        p.name
        for p in data_dir.iterdir()
        if p.is_dir() and _FOLDER_NAME_RE.match(p.name) and not p.name.startswith(".")
    )


# -- Thumbnails: disk-cached, lazy-generated --------------------------------


def _thumb_cache_dir(data_dir: Path) -> Path:
    return data_dir / THUMB_DIR


def _thumb_path(data_dir: Path, folder_name: str, filename: str, source: Path) -> Path:
    """Cached-thumbnail path. Keyed by folder + filename + source mtime so a
    re-uploaded image (same name, new bytes) gets a fresh thumbnail."""
    try:
        mtime = int(source.stat().st_mtime)
    except OSError:
        mtime = 0
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", filename)
    return _thumb_cache_dir(data_dir) / f"{folder_name}__{safe}__{mtime}.jpg"


def _ensure_thumbnail(source: Path, dest: Path) -> Path | None:
    """Generate a JPEG thumbnail if missing. Returns dest path or None on failure."""
    if dest.exists():
        return dest
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(source) as img:
            # EXIF transpose so phone photos land right-way-up.
            img = ImageOps.exif_transpose(img)
            img.thumbnail(THUMB_SIZE, Image.Resampling.LANCZOS)
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            tmp = dest.with_suffix(dest.suffix + ".tmp")
            img.save(tmp, format="JPEG", quality=78, optimize=True)
            os.replace(tmp, dest)
        return dest
    except (OSError, Image.UnidentifiedImageError, ValueError):
        return None


def _all_folder_names(data_dir: Path) -> list[str]:
    """Internal-on-disk folders ∪ external folders declared in metadata."""
    internal = set(_list_internal_folders(data_dir))
    meta = _load_meta(data_dir)
    external = {n for n, m in meta.items() if m.get("external_path")}
    return sorted(internal | external)


# -- Orientation cache: w/h/mtime per image -------------------------------
# Reading dimensions costs a Pillow open; we cache the result keyed by
# (folder, filename, mtime) so re-renders are free and re-uploaded files
# bust the cache automatically.


def _orient_cache_path(data_dir: Path) -> Path:
    return data_dir / ORIENT_CACHE_FILE


def _load_orient_cache(data_dir: Path) -> dict[str, dict[str, Any]]:
    path = _orient_cache_path(data_dir)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_orient_cache(data_dir: Path, cache: dict[str, dict[str, Any]]) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    tmp = _orient_cache_path(data_dir).with_suffix(".json.tmp")
    try:
        tmp.write_text(json.dumps(cache, separators=(",", ":")))
        os.replace(tmp, _orient_cache_path(data_dir))
    except OSError:
        pass


def _orientation_of(source: Path) -> tuple[int, int, str] | None:
    """Read (w, h, orientation) from disk. ``orientation`` is one of
    ``"portrait"``, ``"landscape"``, ``"square"``."""
    try:
        with Image.open(source) as img:
            img = ImageOps.exif_transpose(img)
            w, h = img.size
    except (OSError, Image.UnidentifiedImageError, ValueError):
        return None
    if h == 0:
        return None
    ratio = w / h
    if abs(ratio - 1.0) <= SQUARE_TOLERANCE:
        orient = "square"
    elif ratio > 1:
        orient = "landscape"
    else:
        orient = "portrait"
    return w, h, orient


def _filter_by_orientation(
    images: list[Path],
    folder_segment: str,
    desired: str,
    data_dir: Path,
) -> list[Path]:
    """Return only images whose orientation matches ``desired`` ('portrait',
    'landscape', or 'square'). Uses + updates the on-disk cache."""
    cache = _load_orient_cache(data_dir)
    dirty = False
    kept: list[Path] = []
    for p in images:
        try:
            mtime = int(p.stat().st_mtime)
        except OSError:
            continue
        key = f"{folder_segment}/{p.name}"
        entry = cache.get(key)
        if not entry or entry.get("mtime") != mtime:
            measured = _orientation_of(p)
            if measured is None:
                # Unreadable image — record nothing, but don't bail out either.
                continue
            w, h, orient = measured
            entry = {"mtime": mtime, "w": w, "h": h, "orientation": orient}
            cache[key] = entry
            dirty = True
        if entry["orientation"] == desired:
            kept.append(p)
    if dirty:
        _save_orient_cache(data_dir, cache)
    return kept


# -- Plugin contract: fetch + choices ---------------------------------------


def fetch(
    options: dict[str, Any], settings: dict[str, Any], *, ctx: dict[str, Any]
) -> dict[str, Any]:
    data_dir = Path(ctx["data_dir"])
    folder_name = options.get("folder", "")
    folder = _folder_path(folder_name, data_dir)
    images = _list_images(folder)
    if not images:
        msg = (
            f"No images in '{folder_name or ROOT_FOLDER_VALUE}'. "
            f"Add some via /plugins/gallery/."
        )
        return {"error": msg, "url": None}

    folder_segment = folder_name if folder_name else ROOT_FOLDER_VALUE
    orientation = (options.get("orientation") or "any").lower()
    if orientation in ("portrait", "landscape", "square"):
        images = _filter_by_orientation(images, folder_segment, orientation, data_dir)
        if not images:
            return {
                "error": (
                    f"No {orientation} images in "
                    f"'{folder_name or ROOT_FOLDER_VALUE}'."
                ),
                "url": None,
            }

    mode = options.get("mode", "random")
    if mode == "sequential":
        orient_suffix = f"_{orientation}" if orientation != "any" else ""
        idx_file = data_dir / f".sequential_index_{folder_segment}{orient_suffix}"
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
        "url": f"/plugins/gallery/folders/{folder_segment}/{chosen.name}",
        "filename": chosen.name,
        "folder": folder_segment,
        "count": len(images),
    }


def choices(name: str) -> list[dict[str, Any]]:
    if name != "folders":
        return []
    data_dir = _data_dir()
    out: list[dict[str, Any]] = []
    # Root pseudo-folder: only if there are images directly under data_dir.
    if any(
        p.is_file() and p.suffix.lower() in ALLOWED_SUFFIXES
        for p in (data_dir.iterdir() if data_dir.exists() else [])
    ):
        out.append({"value": ROOT_FOLDER_VALUE, "label": "(root)"})
    meta = _load_meta(data_dir)
    for folder_name in _all_folder_names(data_dir):
        ext = meta.get(folder_name, {}).get("external_path")
        count = len(_list_images(_folder_path(folder_name, data_dir)))
        suffix = " ↗" if ext else ""
        out.append({"value": folder_name, "label": f"{folder_name} ({count}){suffix}"})
    if not out:
        out.append({"value": "", "label": "(no folders yet)"})
    return out


_PAGE_TEMPLATE = """
<!doctype html>
<html lang="en"><head>
  <meta charset="utf-8">
  <title>Gallery — Inky Dash</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="/static/icons/phosphor.css">
  <link rel="stylesheet" href="/static/style/tokens.css">
  <script>
    (function () {
      try {
        var theme = localStorage.getItem('inky_theme') || 'auto';
        var accent = localStorage.getItem('inky_accent');
        var root = document.documentElement;
        var isDark =
          theme === 'dark' ||
          (theme === 'auto' &&
            window.matchMedia &&
            window.matchMedia('(prefers-color-scheme: dark)').matches);
        if (isDark) root.dataset.theme = 'dark';
        else root.removeAttribute('data-theme');
        if (accent) root.style.setProperty('--id-accent', accent);
      } catch (_) {}
    })();
  </script>
</head><body>
  <script type="module" src="/static/dist/gallery-admin.js"></script>
</body></html>
"""


def _folder_summary(folder_name: str, data_dir: Path) -> dict[str, Any]:
    """Build the JSON record the admin UI consumes for one folder."""
    meta = _load_meta(data_dir).get(folder_name, {})
    label = meta.get("label", folder_name)
    external_path = meta.get("external_path")
    folder_path = _folder_path(folder_name, data_dir)
    images = _list_images(folder_path)
    return {
        "name": folder_name,
        "label": label,
        "external_path": external_path,
        "image_count": len(images),
        "images": [
            {
                "name": p.name,
                "url": f"/plugins/gallery/folders/{folder_name}/{p.name}",
                "thumb_url": f"/plugins/gallery/folders/{folder_name}/{p.name}/thumb",
            }
            for p in images
        ],
    }


def blueprint() -> Blueprint:
    bp = Blueprint("gallery_admin", __name__)

    @bp.get("/")
    def index() -> str:
        return render_template_string(_PAGE_TEMPLATE)

    # ---- Image serving ------------------------------------------------------

    @bp.get("/folders/<folder>/<path:filename>")
    def serve_image(folder: str, filename: str) -> Any:
        data_dir = _data_dir()
        target_dir = _folder_path(folder, data_dir)
        if target_dir is None or not target_dir.exists() or not target_dir.is_dir():
            abort(404)
        return send_from_directory(target_dir, filename)

    @bp.get("/folders/<folder>/<path:filename>/thumb")
    def serve_thumbnail(folder: str, filename: str) -> Any:
        """Serve (and lazily generate) a JPEG thumbnail. Long Cache-Control
        means the browser only re-fetches when the cache key changes."""
        data_dir = _data_dir()
        target_dir = _folder_path(folder, data_dir)
        if target_dir is None or not target_dir.exists() or not target_dir.is_dir():
            abort(404)
        safe = secure_filename(filename)
        if not safe:
            abort(404)
        source = target_dir / safe
        if not source.is_file() or source.suffix.lower() not in ALLOWED_SUFFIXES:
            abort(404)
        thumb = _thumb_path(data_dir, folder, safe, source)
        result = _ensure_thumbnail(source, thumb)
        if result is None:
            # Fallback: serve the original. Slower, but never breaks the UI.
            return send_from_directory(target_dir, safe)
        response = send_file(result, mimetype="image/jpeg", conditional=True)
        # Browser caches for a year — the URL embeds the source mtime, so a
        # re-upload busts the cache automatically.
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    # ---- Folder CRUD --------------------------------------------------------

    @bp.get("/api/folders")
    def api_folders() -> Any:
        data_dir = _data_dir()
        out: list[dict[str, Any]] = []
        # Root pseudo-folder
        root_imgs = [
            p
            for p in (data_dir.iterdir() if data_dir.exists() else [])
            if p.is_file() and p.suffix.lower() in ALLOWED_SUFFIXES
        ]
        if root_imgs:
            out.append(
                {
                    "name": ROOT_FOLDER_VALUE,
                    "label": "(root)",
                    "external_path": None,
                    "image_count": len(root_imgs),
                    "images": [
                        {
                            "name": p.name,
                            "url": f"/plugins/gallery/folders/{ROOT_FOLDER_VALUE}/{p.name}",
                            "thumb_url": f"/plugins/gallery/folders/{ROOT_FOLDER_VALUE}/{p.name}/thumb",
                        }
                        for p in sorted(root_imgs)
                    ],
                }
            )
        for folder_name in _all_folder_names(data_dir):
            out.append(_folder_summary(folder_name, data_dir))
        return jsonify(out)

    @bp.post("/api/folders")
    def api_create_folder() -> Any:
        body = request.get_json(silent=True) or {}
        name = (body.get("name") or "").strip().lower()
        if not _FOLDER_NAME_RE.match(name):
            return (
                jsonify({"error": "name must be lowercase letters / digits / - / _"}),
                400,
            )
        data_dir = _data_dir()
        external_path_raw = (body.get("external_path") or "").strip()
        meta = _load_meta(data_dir)
        if name in meta or (data_dir / name).exists():
            return jsonify({"error": "folder already exists"}), 409

        if external_path_raw:
            ext = Path(external_path_raw).expanduser()
            try:
                ext_resolved = ext.resolve()
            except OSError:
                return jsonify({"error": "could not resolve external path"}), 400
            if not ext_resolved.exists():
                return jsonify({"error": f"path does not exist: {ext_resolved}"}), 400
            if not ext_resolved.is_dir():
                return jsonify({"error": f"path is not a directory: {ext_resolved}"}), 400
            meta[name] = {"label": name, "external_path": str(ext_resolved)}
            _save_meta(data_dir, meta)
        else:
            (data_dir / name).mkdir(parents=True)
            meta[name] = {"label": name, "external_path": None}
            _save_meta(data_dir, meta)

        return jsonify(_folder_summary(name, data_dir))

    @bp.delete("/api/folders/<folder>")
    def api_delete_folder(folder: str) -> Any:
        data_dir = _data_dir()
        if folder == ROOT_FOLDER_VALUE:
            return jsonify({"error": "cannot delete the root pseudo-folder"}), 403
        meta = _load_meta(data_dir)
        if folder in meta and meta[folder].get("external_path"):
            # External: just drop the entry; never touch the user's directory.
            del meta[folder]
            _save_meta(data_dir, meta)
            return ("", 204)
        target = data_dir / folder
        if not target.exists() or not target.is_dir() or target == data_dir:
            # Maybe the meta entry exists but the directory was deleted out of band — clean it up.
            if folder in meta:
                del meta[folder]
                _save_meta(data_dir, meta)
                return ("", 204)
            return ("", 404)
        shutil.rmtree(target, ignore_errors=True)
        if folder in meta:
            del meta[folder]
            _save_meta(data_dir, meta)
        return ("", 204)

    # ---- Image upload + delete ---------------------------------------------

    @bp.post("/api/folders/<folder>/images")
    def api_upload(folder: str) -> Any:
        data_dir = _data_dir()
        if folder != ROOT_FOLDER_VALUE and _is_external(folder, data_dir):
            return (
                jsonify({"error": "uploads to external folders aren't allowed"}),
                403,
            )
        target_dir = _folder_path(folder, data_dir)
        # Auto-create internal folder if missing
        if folder != ROOT_FOLDER_VALUE and (target_dir is None or not target_dir.exists()):
            if not _FOLDER_NAME_RE.match(folder):
                return jsonify({"error": "invalid folder name"}), 400
            target_dir = data_dir / folder
            target_dir.mkdir(parents=True, exist_ok=True)
            meta = _load_meta(data_dir)
            meta.setdefault(folder, {"label": folder, "external_path": None})
            _save_meta(data_dir, meta)
        if target_dir is None or not target_dir.exists() or not target_dir.is_dir():
            return ("", 404)
        files = request.files.getlist("file")
        if not files:
            return jsonify({"error": "no files in upload"}), 400
        saved: list[str] = []
        skipped: list[str] = []
        for upload in files:
            if not upload or not upload.filename:
                continue
            safe_name = secure_filename(upload.filename)
            if not safe_name:
                skipped.append(upload.filename)
                continue
            ext_suffix = Path(safe_name).suffix.lower()
            if ext_suffix not in ALLOWED_SUFFIXES:
                skipped.append(safe_name)
                continue
            blob = upload.read(MAX_UPLOAD_BYTES + 1)
            if len(blob) > MAX_UPLOAD_BYTES:
                skipped.append(f"{safe_name} (too large)")
                continue
            (target_dir / safe_name).write_bytes(blob)
            saved.append(safe_name)
        return jsonify({"saved": saved, "skipped": skipped})

    @bp.delete("/api/folders/<folder>/images/<path:filename>")
    def api_delete_image(folder: str, filename: str) -> Any:
        data_dir = _data_dir()
        if folder != ROOT_FOLDER_VALUE and _is_external(folder, data_dir):
            return (
                jsonify({"error": "deletes to external folders aren't allowed"}),
                403,
            )
        target_dir = _folder_path(folder, data_dir)
        if target_dir is None:
            return ("", 404)
        safe = secure_filename(filename)
        if not safe:
            return ("", 404)
        path = target_dir / safe
        if not path.exists() or not path.is_file():
            return ("", 404)
        path.unlink()
        return ("", 204)

    return bp

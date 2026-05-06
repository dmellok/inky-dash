from __future__ import annotations

import hashlib
from pathlib import Path

from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}


class UploadError(Exception):
    """Raised for unsupported / empty / too-large uploads."""


class UploadStore:
    """Content-addressed image store. Files saved as `<sha256_prefix><ext>`."""

    def __init__(self, dir_path: Path):
        self.dir = dir_path
        self.dir.mkdir(parents=True, exist_ok=True)

    def save(self, fs: FileStorage, *, max_bytes: int) -> dict:
        if fs is None or not fs.filename:
            raise UploadError("no file uploaded")
        clean = secure_filename(fs.filename) or "upload"
        ext = self._validated_ext(clean)
        return self._save_stream(fs.stream.read, ext, original_name=clean, max_bytes=max_bytes)

    def save_bytes(self, data: bytes, *, ext: str, original_name: str = "url-upload", max_bytes: int) -> dict:
        ext = ext.lower()
        if ext not in ALLOWED_EXTS:
            raise UploadError(
                f"unsupported extension '{ext}'; allowed: {sorted(ALLOWED_EXTS)}"
            )
        if len(data) == 0:
            raise UploadError("upload is empty")
        if len(data) > max_bytes:
            raise UploadError(f"upload exceeds {max_bytes} bytes")
        digest = hashlib.sha256(data).hexdigest()[:12]
        filename = f"{digest}{ext}"
        target = self.dir / filename
        if not target.exists():
            target.write_bytes(data)
        return {
            "id": filename,
            "filename": filename,
            "original_name": original_name,
            "size": len(data),
        }

    @staticmethod
    def _validated_ext(name: str) -> str:
        ext = Path(name).suffix.lower()
        if ext not in ALLOWED_EXTS:
            raise UploadError(
                f"unsupported extension '{ext}'; allowed: {sorted(ALLOWED_EXTS)}"
            )
        return ext

    def _save_stream(self, read, ext: str, *, original_name: str, max_bytes: int) -> dict:
        tmp = self.dir / f"_pending{ext}"
        sha = hashlib.sha256()
        size = 0
        try:
            with tmp.open("wb") as out:
                while True:
                    chunk = read(64 * 1024)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > max_bytes:
                        raise UploadError(
                            f"upload exceeds {max_bytes} bytes (got at least {size})"
                        )
                    sha.update(chunk)
                    out.write(chunk)
            if size == 0:
                raise UploadError("uploaded file is empty")
            digest = sha.hexdigest()[:12]
            filename = f"{digest}{ext}"
            target = self.dir / filename
            if target.exists():
                tmp.unlink()
            else:
                tmp.replace(target)
        except UploadError:
            tmp.unlink(missing_ok=True)
            raise
        except Exception:
            tmp.unlink(missing_ok=True)
            raise
        return {
            "id": filename,
            "filename": filename,
            "original_name": original_name,
            "size": size,
        }

    def path(self, filename: str) -> Path | None:
        # Reject path traversal / hidden files; only files directly inside self.dir.
        if not filename or "/" in filename or "\\" in filename or filename.startswith("."):
            return None
        p = self.dir / filename
        if not p.is_file():
            return None
        if p.suffix.lower() not in ALLOWED_EXTS:
            return None
        # Resolve & confirm the file lives under self.dir (defence in depth).
        try:
            p.resolve().relative_to(self.dir.resolve())
        except ValueError:
            return None
        return p

    def list_recent(self, limit: int = 30) -> list[dict]:
        out: list[dict] = []
        for p in sorted(self.dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if not p.is_file() or p.suffix.lower() not in ALLOWED_EXTS:
                continue
            out.append({
                "id": p.name,
                "size": p.stat().st_size,
                "mtime": p.stat().st_mtime,
            })
            if len(out) >= limit:
                break
        return out

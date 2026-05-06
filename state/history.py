from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any


class HistoryStore:
    """SQLite-backed push log. One row per push attempt (success or failure)."""

    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._lock, self._conn() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS pushes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    source TEXT NOT NULL,
                    page_id TEXT,
                    draft_id TEXT,
                    source_image TEXT,
                    render_filename TEXT NOT NULL,
                    wire_payload TEXT NOT NULL,
                    duration_s REAL NOT NULL,
                    result TEXT NOT NULL,
                    error TEXT,
                    publish_rc INTEGER
                )
                """
            )
            c.execute("CREATE INDEX IF NOT EXISTS idx_pushes_ts ON pushes(ts DESC)")

    def record(
        self,
        *,
        ts: str,
        source: str,
        render_filename: str,
        wire_payload: dict[str, Any],
        duration_s: float,
        result: str,
        page_id: str | None = None,
        draft_id: str | None = None,
        source_image: str | None = None,
        error: str | None = None,
        publish_rc: int | None = None,
    ) -> int:
        with self._lock, self._conn() as c:
            cur = c.execute(
                """
                INSERT INTO pushes
                  (ts, source, page_id, draft_id, source_image,
                   render_filename, wire_payload, duration_s, result, error, publish_rc)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts,
                    source,
                    page_id,
                    draft_id,
                    source_image,
                    render_filename,
                    json.dumps(wire_payload, separators=(",", ":")),
                    duration_s,
                    result,
                    error,
                    publish_rc,
                ),
            )
            return cur.lastrowid

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock, self._conn() as c:
            rows = c.execute(
                "SELECT * FROM pushes ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def get(self, push_id: int) -> dict[str, Any] | None:
        with self._lock, self._conn() as c:
            row = c.execute(
                "SELECT * FROM pushes WHERE id = ?", (push_id,)
            ).fetchone()
        return _row_to_dict(row) if row else None

    def delete(self, push_id: int) -> str | None:
        """Delete a single push row. Returns the row's render_filename so the
        caller can unlink the matching PNG; None if no row was deleted."""
        with self._lock, self._conn() as c:
            row = c.execute(
                "SELECT render_filename FROM pushes WHERE id = ?", (push_id,)
            ).fetchone()
            if row is None:
                return None
            c.execute("DELETE FROM pushes WHERE id = ?", (push_id,))
            return row["render_filename"]

    def clear(self) -> list[str]:
        """Wipe the whole table. Returns every distinct render_filename so the
        caller can clean up the renders directory."""
        with self._lock, self._conn() as c:
            rows = c.execute(
                "SELECT DISTINCT render_filename FROM pushes"
            ).fetchall()
            c.execute("DELETE FROM pushes")
        return [r["render_filename"] for r in rows if r["render_filename"]]


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    try:
        d["wire_payload"] = json.loads(d["wire_payload"])
    except (TypeError, ValueError):
        d["wire_payload"] = {}
    return d

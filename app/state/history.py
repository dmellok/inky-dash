"""SQLite-backed push history.

Every call to ``PushManager.push`` records a row, regardless of outcome
(sent / failed / busy). Schema is tiny on purpose: we only care about
recent activity, not analytics.

mypy --strict applies via ``app.state.*``.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class HistoryRecord:
    id: int
    ts: datetime
    page_id: str
    digest: str | None
    status: str
    duration_s: float
    error: str | None
    options: dict[str, Any]
    # The MQTT payload that was actually published (or attempted) — useful
    # for debugging "why isn't the panel updating?" by showing exactly what
    # we sent to the broker. Empty dict means no publish was attempted.
    payload: dict[str, Any]
    topic: str | None


class HistoryStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.path))
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pushes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    page_id TEXT NOT NULL,
                    digest TEXT,
                    status TEXT NOT NULL,
                    duration_s REAL NOT NULL,
                    error TEXT,
                    options_json TEXT NOT NULL
                )
                """
            )
            # Forward-compatible additions: ALTER on a pre-existing DB so
            # users who upgrade in place don't get a schema crash. SQLite has
            # no IF NOT EXISTS for ADD COLUMN, so check pragma first.
            cols = {row[1] for row in conn.execute("PRAGMA table_info(pushes)").fetchall()}
            if "payload_json" not in cols:
                conn.execute("ALTER TABLE pushes ADD COLUMN payload_json TEXT")
            if "topic" not in cols:
                conn.execute("ALTER TABLE pushes ADD COLUMN topic TEXT")

    def record(
        self,
        *,
        page_id: str,
        digest: str | None,
        status: str,
        duration_s: float,
        error: str | None,
        options: dict[str, Any],
        payload: dict[str, Any] | None = None,
        topic: str | None = None,
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO pushes "
                "(ts, page_id, digest, status, duration_s, error, options_json, payload_json, topic) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    datetime.now(UTC).isoformat(),
                    page_id,
                    digest,
                    status,
                    duration_s,
                    error,
                    json.dumps(options),
                    json.dumps(payload or {}),
                    topic,
                ),
            )
            inserted_id = cur.lastrowid
            assert inserted_id is not None
            return inserted_id

    def recent(self, limit: int = 50) -> list[HistoryRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, ts, page_id, digest, status, duration_s, error, "
                "options_json, payload_json, topic "
                "FROM pushes ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    @staticmethod
    def _row_to_record(row: tuple[Any, ...]) -> HistoryRecord:
        options_raw = json.loads(row[7])
        if not isinstance(options_raw, dict):
            options_raw = {}
        # row[8] (payload_json) may be NULL on rows written before the
        # schema added the column; default to empty dict.
        payload_raw: dict[str, Any] = {}
        if row[8]:
            try:
                parsed = json.loads(row[8])
                if isinstance(parsed, dict):
                    payload_raw = parsed
            except json.JSONDecodeError:
                pass
        return HistoryRecord(
            id=int(row[0]),
            ts=datetime.fromisoformat(row[1]),
            page_id=str(row[2]),
            digest=row[3],
            status=str(row[4]),
            duration_s=float(row[5]),
            error=row[6],
            options=options_raw,
            payload=payload_raw,
            topic=row[9],
        )

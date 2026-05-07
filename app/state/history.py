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

    def record(
        self,
        *,
        page_id: str,
        digest: str | None,
        status: str,
        duration_s: float,
        error: str | None,
        options: dict[str, Any],
    ) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO pushes (ts, page_id, digest, status, duration_s, error, options_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    datetime.now(UTC).isoformat(),
                    page_id,
                    digest,
                    status,
                    duration_s,
                    error,
                    json.dumps(options),
                ),
            )
            inserted_id = cur.lastrowid
            assert inserted_id is not None
            return inserted_id

    def recent(self, limit: int = 50) -> list[HistoryRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, ts, page_id, digest, status, duration_s, error, options_json "
                "FROM pushes ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_record(r) for r in rows]

    @staticmethod
    def _row_to_record(row: tuple[Any, ...]) -> HistoryRecord:
        options_raw = json.loads(row[7])
        if not isinstance(options_raw, dict):
            options_raw = {}
        return HistoryRecord(
            id=int(row[0]),
            ts=datetime.fromisoformat(row[1]),
            page_id=str(row[2]),
            digest=row[3],
            status=str(row[4]),
            duration_s=float(row[5]),
            error=row[6],
            options=options_raw,
        )

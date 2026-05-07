"""Persistent state: page model, page store, future schedules + history.

mypy --strict applies to ``app.state.*`` per v4-brief §6.
"""

from __future__ import annotations

from app.state.history import HistoryRecord, HistoryStore
from app.state.page_model import Cell, Page, Panel
from app.state.page_store import PageStore

__all__ = ["Cell", "HistoryRecord", "HistoryStore", "Page", "PageStore", "Panel"]

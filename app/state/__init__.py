"""Persistent state: page model, page store, future schedules + history.

mypy --strict applies to ``app.state.*`` per v4-brief §6.
"""

from __future__ import annotations

from app.state.app_settings import (
    PANEL_MODELS,
    AppSettings,
    AppSettingsStore,
    MqttSettings,
    PanelModelSpec,
    PanelSettings,
)
from app.state.history import HistoryRecord, HistoryStore
from app.state.page_model import Cell, Page, Panel
from app.state.page_store import PageStore
from app.state.schedule_model import Schedule
from app.state.schedule_store import ScheduleStore
from app.state.settings_store import SettingsStore

__all__ = [
    "PANEL_MODELS",
    "AppSettings",
    "AppSettingsStore",
    "Cell",
    "HistoryRecord",
    "HistoryStore",
    "MqttSettings",
    "Page",
    "PageStore",
    "Panel",
    "PanelModelSpec",
    "PanelSettings",
    "Schedule",
    "ScheduleStore",
    "SettingsStore",
]

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.state import Schedule


def _interval(**overrides):
    base = {
        "id": "morning",
        "name": "Morning",
        "page_id": "_demo",
        "type": "interval",
        "interval_minutes": 60,
    }
    base.update(overrides)
    return base


def _oneshot(**overrides):
    base = {
        "id": "fri",
        "name": "Friday",
        "page_id": "_demo",
        "type": "oneshot",
        "fires_at": datetime(2026, 12, 25, 9, 0, tzinfo=UTC),
    }
    base.update(overrides)
    return base


def test_interval_requires_minutes() -> None:
    with pytest.raises(ValidationError):
        Schedule.model_validate({"id": "x", "name": "x", "page_id": "_demo", "type": "interval"})


def test_oneshot_requires_fires_at() -> None:
    with pytest.raises(ValidationError):
        Schedule.model_validate({"id": "x", "name": "x", "page_id": "_demo", "type": "oneshot"})


def test_dow_must_be_in_range() -> None:
    with pytest.raises(ValidationError):
        Schedule.model_validate(_interval(days_of_week=[7]))


def test_dow_dedupe_and_sort() -> None:
    s = Schedule.model_validate(_interval(days_of_week=[5, 1, 3, 1]))
    assert s.days_of_week == [1, 3, 5]


def test_hhmm_format_strict() -> None:
    with pytest.raises(ValidationError):
        Schedule.model_validate(_interval(time_of_day_start="9:30"))
    with pytest.raises(ValidationError):
        Schedule.model_validate(_interval(time_of_day_start="24:00"))
    Schedule.model_validate(_interval(time_of_day_start="09:30", time_of_day_end="17:00"))


def test_oneshot_can_be_constructed() -> None:
    s = Schedule.model_validate(_oneshot())
    assert s.fires_at is not None
    assert s.fired is False


def test_extra_fields_rejected() -> None:
    with pytest.raises(ValidationError):
        Schedule.model_validate(_interval(rogue_field="oops"))

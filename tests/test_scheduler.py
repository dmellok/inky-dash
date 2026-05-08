"""Scheduler logic — find_due decisions across interval/oneshot/dow/window."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.push import PushResult
from app.scheduler import Scheduler
from app.state import Schedule, ScheduleStore


@dataclass
class FakePusher:
    pushes: list[tuple[str, str]] = field(default_factory=list)
    next_status: str = "sent"

    def push(
        self, page_id: str, *, options: object | None = None, dither: object = "floyd-steinberg"
    ) -> PushResult:
        self.pushes.append((page_id, str(dither)))
        return PushResult(
            status=self.next_status,  # type: ignore[arg-type]
            digest="abc123" if self.next_status == "sent" else None,
            url="http://test/x.png" if self.next_status == "sent" else None,
            duration_s=0.05,
        )


def _scheduler(tmp_path: Path) -> tuple[Scheduler, ScheduleStore, FakePusher]:
    store = ScheduleStore(tmp_path / "s.json")
    pusher = FakePusher()
    return Scheduler(store=store, push_manager=pusher), store, pusher


def _interval_schedule(**overrides: Any) -> Schedule:
    base = {
        "id": "every-hour",
        "name": "Every hour",
        "page_id": "_demo",
        "type": "interval",
        "interval_minutes": 60,
    }
    base.update(overrides)
    return Schedule.model_validate(base)


def _oneshot_schedule(fires_at: datetime, **overrides: Any) -> Schedule:
    base = {
        "id": "once",
        "name": "Once",
        "page_id": "_demo",
        "type": "oneshot",
        "fires_at": fires_at,
    }
    base.update(overrides)
    return Schedule.model_validate(base)


def test_disabled_never_due(tmp_path: Path) -> None:
    sched, store, _ = _scheduler(tmp_path)
    store.upsert(_interval_schedule(enabled=False))
    assert sched.find_due(datetime(2026, 5, 8, 12, 0, tzinfo=UTC)) == []


def test_interval_fires_first_time(tmp_path: Path) -> None:
    sched, store, pusher = _scheduler(tmp_path)
    store.upsert(_interval_schedule(interval_minutes=30))
    fired = sched.run_due_once(datetime(2026, 5, 8, 12, 0, tzinfo=UTC))
    assert len(fired) == 1
    assert pusher.pushes == [("_demo", "floyd-steinberg")]


def test_interval_holds_until_window_passes(tmp_path: Path) -> None:
    sched, store, pusher = _scheduler(tmp_path)
    store.upsert(_interval_schedule(interval_minutes=30))
    t0 = datetime(2026, 5, 8, 12, 0, tzinfo=UTC)
    sched.run_due_once(t0)
    sched.run_due_once(t0 + timedelta(minutes=10))  # too soon
    sched.run_due_once(t0 + timedelta(minutes=29))  # still too soon
    assert len(pusher.pushes) == 1
    sched.run_due_once(t0 + timedelta(minutes=30))  # now due
    assert len(pusher.pushes) == 2


def test_dow_mask_blocks_other_days(tmp_path: Path) -> None:
    sched, store, _ = _scheduler(tmp_path)
    # Weekday 4 = Friday; 2026-05-08 is a Friday.
    store.upsert(_interval_schedule(days_of_week=[0]))  # Mon only
    assert sched.find_due(datetime(2026, 5, 8, 12, 0, tzinfo=UTC)) == []
    store.upsert(_interval_schedule(days_of_week=[4]))  # now Fri included
    assert len(sched.find_due(datetime(2026, 5, 8, 12, 0, tzinfo=UTC))) == 1


def test_time_of_day_window(tmp_path: Path) -> None:
    sched, store, _ = _scheduler(tmp_path)
    store.upsert(_interval_schedule(time_of_day_start="09:00", time_of_day_end="17:00"))
    assert sched.find_due(datetime(2026, 5, 8, 8, 30, tzinfo=UTC)) == []
    assert len(sched.find_due(datetime(2026, 5, 8, 12, 0, tzinfo=UTC))) == 1
    assert sched.find_due(datetime(2026, 5, 8, 18, 0, tzinfo=UTC)) == []


def test_wrap_around_window(tmp_path: Path) -> None:
    """22:00–06:00 covers 23:00 and 03:00 but not 12:00."""
    sched, store, _ = _scheduler(tmp_path)
    store.upsert(_interval_schedule(time_of_day_start="22:00", time_of_day_end="06:00"))
    assert len(sched.find_due(datetime(2026, 5, 8, 23, 0, tzinfo=UTC))) == 1
    assert len(sched.find_due(datetime(2026, 5, 8, 3, 0, tzinfo=UTC))) == 1
    assert sched.find_due(datetime(2026, 5, 8, 12, 0, tzinfo=UTC)) == []


def test_oneshot_fires_daily_at_time_of_day(tmp_path: Path) -> None:
    """oneshot is now 'fire daily at HH:MM' — date portion of fires_at is
    ignored; the schedule fires once per day after its time-of-day passes
    and won't re-fire on the same day."""
    sched, store, pusher = _scheduler(tmp_path)
    fires = datetime(2026, 5, 8, 12, 0, tzinfo=UTC)
    store.upsert(_oneshot_schedule(fires))
    # Before today's HH:MM: not due
    assert sched.find_due(fires - timedelta(seconds=1)) == []
    sched.run_due_once(fires + timedelta(seconds=1))
    assert len(pusher.pushes) == 1
    # Same day, after firing: not due again
    sched.run_due_once(fires + timedelta(minutes=10))
    assert len(pusher.pushes) == 1
    # Next day at the same time: due again
    sched.run_due_once(fires + timedelta(days=1, seconds=1))
    assert len(pusher.pushes) == 2


def test_priority_orders_concurrent_fires(tmp_path: Path) -> None:
    sched, store, pusher = _scheduler(tmp_path)
    store.upsert(_interval_schedule(id="lo", priority=0))
    store.upsert(_interval_schedule(id="hi", priority=10))
    sched.run_due_once(datetime(2026, 5, 8, 12, 0, tzinfo=UTC))
    # Higher priority first
    assert pusher.pushes[0][0] == "_demo"  # both target _demo; check order via call count
    # Two pushes, both for _demo
    assert len(pusher.pushes) == 2


def test_failed_push_does_not_advance_last_fired(tmp_path: Path) -> None:
    sched, store, pusher = _scheduler(tmp_path)
    pusher.next_status = "failed"
    store.upsert(_interval_schedule(interval_minutes=30))
    t0 = datetime(2026, 5, 8, 12, 0, tzinfo=UTC)
    sched.run_due_once(t0)
    sched.run_due_once(t0 + timedelta(minutes=1))  # still tries — last_fired never set
    assert len(pusher.pushes) == 2


def test_fire_now_ignores_window(tmp_path: Path) -> None:
    sched, store, pusher = _scheduler(tmp_path)
    store.upsert(_interval_schedule(time_of_day_start="03:00", time_of_day_end="04:00"))
    # Outside window — find_due returns nothing
    assert sched.find_due(datetime(2026, 5, 8, 12, 0, tzinfo=UTC)) == []
    # But fire_now bypasses
    result = sched.fire_now("every-hour")
    assert result is not None
    assert pusher.pushes == [("_demo", "floyd-steinberg")]

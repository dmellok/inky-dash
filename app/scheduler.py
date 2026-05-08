"""Background scheduler — fires schedules whose time has come.

Runs as a daemon thread. On each tick (default every 30s) it:
1. Loads schedules from the store
2. Filters to those that are enabled AND match the day-of-week mask AND the
   time-of-day window AND have come due (interval elapsed, or one-shot time
   reached)
3. Sorts by priority (high first) and fires them in order via PushManager

Concurrent pushes are not a concern at this layer — PushManager itself is
single-flight, so concurrent ``push_page`` calls serialize.

Last-fire times are kept in memory only. After a restart, the next tick treats
every interval schedule as "never fired" and may fire one immediately.
That's the simpler design; persisting last_fired is an obvious upgrade if
double-fires-on-restart become a problem.
"""

from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime, time

from app.push import PushManager, PushResult
from app.state.schedule_model import Schedule
from app.state.schedule_store import ScheduleStore

logger = logging.getLogger(__name__)


def _matches_dow(schedule: Schedule, now: datetime) -> bool:
    # Python weekday: Monday = 0 ... Sunday = 6 — same as our schedule mask.
    return now.weekday() in schedule.days_of_week


def _matches_window(schedule: Schedule, now: datetime) -> bool:
    if schedule.time_of_day_start is None and schedule.time_of_day_end is None:
        return True
    current = now.time()
    start = _parse_hhmm(schedule.time_of_day_start) if schedule.time_of_day_start else time(0, 0)
    end = _parse_hhmm(schedule.time_of_day_end) if schedule.time_of_day_end else time(23, 59, 59)
    if start <= end:
        return start <= current <= end
    # Wrap-around window (e.g. 22:00–06:00).
    return current >= start or current <= end


def _parse_hhmm(value: str) -> time:
    h, m = value.split(":")
    return time(int(h), int(m))


class Scheduler:
    def __init__(
        self,
        *,
        store: ScheduleStore,
        push_manager: PushManager,
        tick_seconds: int = 30,
    ) -> None:
        self._store = store
        self._push = push_manager
        self._tick = tick_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        # In-memory: schedule_id → last fired POSIX timestamp.
        self._last_fired: dict[str, float] = {}
        self._lock = threading.Lock()

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        thread = threading.Thread(target=self._run, name="inky-scheduler", daemon=True)
        thread.start()
        self._thread = thread

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._tick_once(datetime.now(UTC))
            except Exception:
                logger.exception("scheduler tick crashed")
            self._stop.wait(self._tick)

    def find_due(self, now: datetime | None = None) -> list[Schedule]:
        """Pure function: returns schedules that should fire at ``now``.

        Public for tests and the manual ``run_due`` helper. Sorted by priority
        descending, then id for stable ordering.
        """
        now = now or datetime.now(UTC)
        candidates: list[Schedule] = []
        for s in self._store.all():
            if not s.enabled:
                continue
            # oneshot is now "fire daily at this time" — bypass the dow +
            # window filters entirely. interval schedules still respect them.
            if s.type == "interval":
                if not _matches_dow(s, now):
                    continue
                if not _matches_window(s, now):
                    continue
                if s.interval_minutes is None:
                    continue
                with self._lock:
                    last = self._last_fired.get(s.id)
                if last is None or (now.timestamp() - last) >= s.interval_minutes * 60:
                    candidates.append(s)
            elif s.type == "oneshot":
                if s.fires_at is None:
                    continue
                # Today's "fires_at" — only the time-of-day matters.
                target = now.replace(
                    hour=s.fires_at.hour,
                    minute=s.fires_at.minute,
                    second=0,
                    microsecond=0,
                )
                if now < target:
                    continue
                with self._lock:
                    last = self._last_fired.get(s.id)
                if last is not None:
                    last_dt = datetime.fromtimestamp(last, tz=UTC)
                    if last_dt.date() == now.date():
                        continue  # already fired today
                candidates.append(s)
        candidates.sort(key=lambda s: (-s.priority, s.id))
        return candidates

    def _tick_once(self, now: datetime) -> None:
        for schedule in self.find_due(now):
            self._fire(schedule, now)

    def _fire(self, schedule: Schedule, now: datetime) -> PushResult:
        logger.info("Firing schedule %s → page %s", schedule.id, schedule.page_id)
        result = self._push.push(schedule.page_id, dither=schedule.dither)
        if result.status == "sent":
            # last_fired tracks "did we already fire today" for oneshot/daily
            # and "interval cooldown" for interval. Same source of truth.
            with self._lock:
                self._last_fired[schedule.id] = now.timestamp()
        return result

    # -- helpers for tests / manual fire ----------------------------------

    def run_due_once(self, now: datetime | None = None) -> list[tuple[Schedule, PushResult]]:
        """Synchronous one-pass fire-due — used by tests and manual triggers."""
        out: list[tuple[Schedule, PushResult]] = []
        when = now or datetime.now(UTC)
        for s in self.find_due(when):
            out.append((s, self._fire(s, when)))
        return out

    def fire_now(self, schedule_id: str) -> PushResult | None:
        s = self._store.get(schedule_id)
        if s is None:
            return None
        return self._fire(s, datetime.now(UTC))

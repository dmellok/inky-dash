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


def _local(now: datetime) -> datetime:
    """Convert a UTC-aware ``datetime`` to the server's local clock so that
    weekday + HH:MM comparisons match what the user typed in the editor.
    The editor's time pickers don't carry a timezone; we treat them as
    local-wall-clock for the host running the companion."""
    return now.astimezone()


def _matches_dow(schedule: Schedule, now: datetime) -> bool:
    # Python weekday: Monday = 0 ... Sunday = 6 — same as our schedule mask.
    return _local(now).weekday() in schedule.days_of_week


def _matches_window(schedule: Schedule, now: datetime) -> bool:
    if schedule.time_of_day_start is None and schedule.time_of_day_end is None:
        return True
    current = _local(now).time()
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
        # When we first observed each enabled schedule. Cleared if the
        # schedule gets disabled or removed, so a re-enable later starts a
        # fresh "we're watching" window. Used to suppress oneshot backfills:
        # if today's target was before we started watching, the next fire
        # is tomorrow, not "right now playing catch-up."
        self._first_seen: dict[str, float] = {}
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
        """Return schedules that should fire at ``now``, sorted by priority
        descending then id. Has a tiny side effect: records each enabled
        schedule's first-observed timestamp so oneshot backfills are
        suppressed (see ``_observe``).
        """
        now = now or datetime.now(UTC)
        self._observe(now)
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
                # Today's "fires_at" — only the time-of-day matters, and it
                # was typed by the user in local-wall-clock terms (no tz in
                # the picker), so build the target in local time before
                # comparing.
                local_now = _local(now)
                target_local = local_now.replace(
                    hour=s.fires_at.hour,
                    minute=s.fires_at.minute,
                    second=0,
                    microsecond=0,
                )
                target = target_local.astimezone(UTC)
                if now < target:
                    continue
                with self._lock:
                    first_seen = self._first_seen.get(s.id)
                    last = self._last_fired.get(s.id)
                # Suppress backfill: if we weren't watching this schedule
                # at the moment today's target would have fired, don't
                # fire it now. Fixes "enabling a schedule mid-day pushes
                # the morning's missed fires through all at once."
                if first_seen is None or first_seen > target.timestamp():
                    continue
                if last is not None:
                    last_dt = datetime.fromtimestamp(last, tz=UTC)
                    if last_dt.astimezone().date() == local_now.date():
                        continue  # already fired today (in local terms)
                candidates.append(s)
        candidates.sort(key=lambda s: (-s.priority, s.id))
        return candidates

    def _tick_once(self, now: datetime) -> None:
        self._observe(now)
        for schedule in self.find_due(now):
            self._fire(schedule, now)

    def _observe(self, now: datetime) -> None:
        """Maintain ``_first_seen``: record the moment we first noticed each
        enabled schedule, and drop entries for ids that are now disabled or
        deleted. Disabling then re-enabling a schedule resets its first-seen
        window so a mid-day re-enable doesn't replay today's earlier targets.
        """
        enabled_ids = {s.id for s in self._store.all() if s.enabled}
        with self._lock:
            for sid in list(self._first_seen):
                if sid not in enabled_ids:
                    del self._first_seen[sid]
            for sid in enabled_ids:
                self._first_seen.setdefault(sid, now.timestamp())

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
        self._observe(when)
        for s in self.find_due(when):
            out.append((s, self._fire(s, when)))
        return out

    def fire_now(self, schedule_id: str) -> PushResult | None:
        s = self._store.get(schedule_id)
        if s is None:
            return None
        return self._fire(s, datetime.now(UTC))

from __future__ import annotations

import sys
import threading
import time
from datetime import datetime, time as dtime
from typing import Any

from push import PushBusy, PushManager, PushValidationError
from state.pages import PageStore
from state.schedules import Schedule, SchedulesStore


class Scheduler:
    """Background thread that fires due schedules through the push pipeline.

    Single tick interval (default 10s) — tight enough to keep interval-minute
    accuracy within tens of seconds, loose enough not to thrash the renderer.
    Each fire is delegated to PushManager which already serialises pushes via
    its render lock; if a render is in flight the scheduler skips this tick
    and tries again next.
    """

    def __init__(
        self,
        store: SchedulesStore,
        pages: PageStore,
        push: PushManager,
        *,
        tick_seconds: float = 10.0,
    ):
        self.store = store
        self.pages = pages
        self.push = push
        self.tick_seconds = tick_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, name="inky-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    # ---------- main loop ---------------------------------------------------

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception as exc:
                print(f"[scheduler] tick failed: {exc}", file=sys.stderr)
            self._stop.wait(self.tick_seconds)

    def tick(self, now: datetime | None = None) -> list[str]:
        """Run one scheduling tick; returns ids of schedules that fired.

        Priority: when multiple schedules are due in the same tick the
        topmost one (earliest in the list, set via the schedules-list drag
        handles) wins. Lower-priority due schedules defer until the next
        tick so the panel doesn't get hammered with back-to-back pushes.
        """
        now = now or datetime.now()
        fired: list[str] = []
        for sched in self.store.list():
            if not sched.enabled:
                continue
            if not self._is_due(sched, now):
                continue
            if self._fire(sched, now):
                fired.append(sched.id)
                # Top-of-stack wins on conflict — break and let lower-priority
                # due schedules try again next tick.
                break
        return fired

    # ---------- decision ----------------------------------------------------

    def _is_due(self, sched: Schedule, now: datetime) -> bool:
        if sched.kind == "one_shot":
            # "One-shot" semantics: fires once per day at HH:MM, optionally
            # restricted by day-of-week. The schedule re-arms daily.
            if sched.days_of_week and now.weekday() not in sched.days_of_week:
                return False
            if not sched.at:
                return False
            try:
                hm = sched.at.split(":")
                h, m = int(hm[0]), int(hm[1])
            except (ValueError, IndexError):
                # Tolerate legacy ISO datetimes by taking the time-of-day part.
                try:
                    h = int(sched.at[11:13])
                    m = int(sched.at[14:16])
                except (ValueError, IndexError):
                    return False
            fire_time_today = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if now < fire_time_today:
                return False
            # Has it already fired today?
            if sched.last_fired_at:
                try:
                    last = datetime.fromisoformat(sched.last_fired_at)
                    if last.date() == now.date():
                        return False
                except (TypeError, ValueError):
                    pass
            return True

        if sched.kind == "interval":
            if sched.days_of_week and now.weekday() not in sched.days_of_week:
                return False
            try:
                start_h, start_m = map(int, sched.start_time.split(":"))
                end_h, end_m = map(int, sched.end_time.split(":"))
            except (TypeError, ValueError):
                return False
            now_t = now.time()
            if not (dtime(start_h, start_m) <= now_t <= dtime(end_h, end_m)):
                return False
            if sched.last_fired_at:
                try:
                    last = datetime.fromisoformat(sched.last_fired_at)
                except (TypeError, ValueError):
                    return True
                # 5s tolerance so a 10s tick doesn't miss the next slot exactly N
                # minutes later — better to fire a couple of seconds early than
                # an entire tick late.
                if (now - last).total_seconds() < sched.every_minutes * 60 - 5:
                    return False
            return True

        return False

    # ---------- execution ---------------------------------------------------

    def _fire(self, sched: Schedule, now: datetime) -> bool:
        """Returns True if the fire was attempted (busy/error count too)."""
        target = sched.target or {}
        if target.get("type") != "page":
            self._record_error(sched, now, f"unsupported target type: {target.get('type')}")
            return True

        page_id = target.get("page_id")
        if not page_id or not self.pages.get(page_id):
            self._record_error(sched, now, f"page not found: {page_id}")
            return True

        try:
            from push import _local_compose_url
            self.push.push(
                source="schedule",
                target={"page_id": page_id, "schedule_id": sched.id},
                options=sched.options,
                compose_url=_local_compose_url(self.push.config, page_id=page_id),
            )
        except PushBusy:
            # Another push is in flight; back off and retry next tick — do not
            # mark as fired so the same slot keeps trying until it lands.
            return False
        except PushValidationError as exc:
            self._record_error(sched, now, f"validation: {exc}")
            return True
        except Exception as exc:
            self._record_error(sched, now, f"{type(exc).__name__}: {exc}")
            return True

        self.store.update_state(
            sched.id,
            last_fired_at=now.isoformat(timespec="seconds"),
            last_result="ok",
            last_error=None,
        )
        return True

    def _record_error(self, sched: Schedule, now: datetime, msg: str) -> None:
        self.store.update_state(
            sched.id,
            last_fired_at=now.isoformat(timespec="seconds"),
            last_result="error",
            last_error=msg,
        )

"""Dev-mode entrypoint for ``python -m app``.

This module deliberately does TWO things that the naive
``create_app().run(debug=True)`` form gets wrong:

1. **Reloader-parent stub.** Flask's debug reloader re-execs this module
   in a child process to serve requests while the parent watches files.
   The naive form calls ``create_app()`` in BOTH processes, which means
   two ``Scheduler`` threads firing the same schedules out of phase, and
   two MQTT clients with the same client_id racing each other off the
   broker. We let the parent run a minimal stub Flask app whose only job
   is to host the reloader; the worker builds the real app.

2. **Orphan protection.** A previous instance can leak past restarts
   (``kill -9`` on the parent leaves the child orphaned and adopted by
   PID 1). Two guards:
     - Before binding port 5555, scan for another ``python -m app``
       holding it and SIGTERM it. Saves the user from "port already in
       use" + invisible double-fires.
     - In the worker, a small daemon thread polls ``os.kill(ppid, 0)``;
       if the parent is gone, the worker exits cleanly instead of
       lingering forever as an orphan.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import threading
import time

PORT = 5555


def _lsof_pids(port: int) -> list[int]:
    """Return PIDs holding ``port`` according to lsof. Empty on macOS/Linux
    if nothing's holding it (lsof returns rc=1 with no output)."""
    try:
        out = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    return [int(line) for line in out.stdout.split() if line.strip().isdigit()]


def _proc_cmd(pid: int) -> str:
    """Return the full command line of ``pid`` or '' on failure."""
    try:
        out = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""
    return out.stdout.strip()


def _evict_stale_instances() -> None:
    """If another ``python -m app`` holds our port, SIGTERM it. Refuse to
    start if a foreign process is holding the port."""
    own = {os.getpid()}
    holders = [pid for pid in _lsof_pids(PORT) if pid not in own]
    if not holders:
        return
    foreign: list[int] = []
    killed: list[int] = []
    for pid in holders:
        cmd = _proc_cmd(pid)
        if "python" in cmd and ("app/__main__" in cmd or "-m app" in cmd or " app " in cmd):
            print(
                f"inky-dash: replacing previous instance pid={pid} ({cmd})",
                file=sys.stderr,
            )
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, signal.SIGTERM)
                killed.append(pid)
        else:
            foreign.append(pid)
    if foreign:
        for pid in foreign:
            print(
                f"inky-dash: port {PORT} held by foreign process pid={pid} ({_proc_cmd(pid)!r})",
                file=sys.stderr,
            )
        print("inky-dash: refusing to start; kill it manually or free the port", file=sys.stderr)
        sys.exit(1)
    # Wait briefly for the SIGTERMed instances to release the port, then
    # SIGKILL anything that hasn't. paho.mqtt-using processes can take a
    # second or two to shut down cleanly.
    for _ in range(20):
        time.sleep(0.1)
        if not any(pid in _lsof_pids(PORT) for pid in killed):
            return
    for pid in killed:
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, signal.SIGKILL)


def _watch_parent(initial_ppid: int) -> None:
    """Daemon thread that exits the process if the original parent dies.

    Without this, ``kill -9`` on the reloader-parent leaves the worker
    (with its Scheduler + MQTT client) running forever — exactly the
    orphan-pattern that produced the double-fires today."""
    while True:
        time.sleep(2)
        try:
            os.kill(initial_ppid, 0)
        except ProcessLookupError:
            sys.stderr.write(f"inky-dash worker: parent pid={initial_ppid} is gone; exiting\n")
            # os._exit instead of sys.exit — we're a daemon thread, raising
            # SystemExit on the main thread doesn't reliably tear us down.
            os._exit(0)
        except PermissionError:
            # Process exists but we can't signal it — shouldn't happen for
            # our own parent, but if it does, assume alive and continue.
            continue


if __name__ == "__main__":
    is_worker = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    no_reload = "--no-reload" in sys.argv

    if is_worker or no_reload:
        # Worker process (or non-reloading run). Build the full app +
        # background services here. The parent-PID watchdog only matters
        # when we actually have a separate parent (i.e. is_worker).
        if is_worker:
            threading.Thread(
                target=_watch_parent,
                args=(os.getppid(),),
                daemon=True,
                name="parent-watchdog",
            ).start()

        from app import create_app

        create_app().run(
            host="0.0.0.0",
            port=PORT,
            debug=True,
            use_reloader=False,  # the parent runs the reloader; we just serve
        )
    else:
        # Reloader parent. Kill any stale ``python -m app`` holding our
        # port first so file-watching restarts don't pile up over weeks
        # of dev. Then host the reloader off a stub Flask app — the
        # parent never serves requests, so it doesn't need our routes,
        # scheduler, or MQTT client.
        _evict_stale_instances()

        from flask import Flask

        Flask("inky-dash-reloader").run(host="0.0.0.0", port=PORT, debug=True)

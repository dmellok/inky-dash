from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path


def _dotenv_keys(path: Path) -> set[str]:
    """Return the keys currently present in .env — these are app-managed and
    must be stripped from the child env so the restarted process reads .env
    fresh instead of inheriting our own stale values via execv."""
    keys: set[str] = set()
    if not path.exists():
        return keys
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        keys.add(line.partition("=")[0].strip())
    return keys


def schedule_restart(host: str, port: int, *, delay: float = 0.3) -> None:
    """Spawn a detached helper that re-execs us once we've released the listening
    socket, then exit the current process.

    Why: os.execv on the running app inherits the bound listening socket FD; the
    new interpreter has no reference to it but the kernel keeps the port held.
    The helper lives in a fresh process group, waits for our PID to exit and the
    port to free, then execs a clean Python with our original argv.
    """
    probe_host = "127.0.0.1" if host in ("0.0.0.0", "::", "") else host
    args = [
        sys.executable,
        "-m",
        "restart_helper",
        str(os.getpid()),
        probe_host,
        str(port),
        "--",
        sys.executable,
        *sys.argv,
    ]
    root = Path(__file__).resolve().parent
    managed = _dotenv_keys(root / ".env")
    child_env = {k: v for k, v in os.environ.items() if k not in managed}
    log_path = os.environ.get("INKY_RESTART_LOG", "/tmp/inky-restart.log")
    log_fh = open(log_path, "ab", buffering=0)
    subprocess.Popen(
        args,
        start_new_session=True,
        close_fds=True,
        stdin=subprocess.DEVNULL,
        stdout=log_fh,
        stderr=log_fh,
        cwd=os.getcwd(),
        env=child_env,
    )
    log_fh.close()
    threading.Timer(delay, lambda: os._exit(0)).start()

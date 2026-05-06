from __future__ import annotations

import os
import socket
import sys
import time


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _port_free(host: str, port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.25)
    try:
        s.connect((host, port))
        s.close()
        return False
    except OSError:
        s.close()
        return True


def _log(msg: str) -> None:
    print(f"[restart_helper {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main() -> None:
    _log(f"started pid={os.getpid()} argv={sys.argv}")
    pid = int(sys.argv[1])
    host = sys.argv[2] or "127.0.0.1"
    port = int(sys.argv[3])
    sep = sys.argv.index("--")
    argv = sys.argv[sep + 1 :]
    _log(f"waiting for parent pid={pid} to exit and {host}:{port} to free")

    deadline = time.time() + 60.0
    while time.time() < deadline:
        alive = _pid_alive(pid)
        free = _port_free(host, port)
        if not alive and free:
            break
        time.sleep(0.1)
    else:
        _log(f"deadline reached; alive={_pid_alive(pid)} free={_port_free(host, port)}")

    _log(f"execv {argv}")
    try:
        os.execv(argv[0], argv)
    except Exception as exc:
        _log(f"execv failed: {exc!r}")
        raise


if __name__ == "__main__":
    main()

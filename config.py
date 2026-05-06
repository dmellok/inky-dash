from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent


def _normalize_base_url(raw: str | None, *, port: int) -> str:
    """Normalize PUBLIC_BASE_URL so the wire payload is always reachable.

    Accepts the user's value in any of:
      - empty/unset                     → http://localhost:<port>
      - "192.168.50.42"                 → http://192.168.50.42:<port>
      - "homelab.lan"                   → http://homelab.lan:<port>
      - "http://homelab.lan"            → http://homelab.lan:<port>
      - "http://homelab.lan:8080"       → http://homelab.lan:8080  (kept)
      - "https://example.com:443/..."   → preserved verbatim minus trailing /

    The port falls back to the bound `PORT` whenever the URL doesn't carry
    one of its own — so users who type just an IP into Settings still get a
    fully-qualified wire URL.
    """
    if not raw or not raw.strip():
        return f"http://localhost:{port}"
    s = raw.strip().rstrip("/")
    if "://" not in s:
        s = "http://" + s
    parsed = urlparse(s)
    host = parsed.hostname
    if not host:
        return f"http://localhost:{port}"
    final_port = parsed.port if parsed.port else port
    scheme = parsed.scheme or "http"
    path = parsed.path or ""
    return f"{scheme}://{host}:{final_port}{path}".rstrip("/")


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("\"", "'"):
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _env(key: str, default: str | None = None) -> str | None:
    raw = os.environ.get(key)
    if raw is None or raw == "":
        return default
    return raw


def _int(key: str, default: int) -> int:
    raw = os.environ.get(key)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    host: str
    port: int
    public_base_url: str

    mqtt_host: str
    mqtt_port: int
    mqtt_username: str | None
    mqtt_password: str | None
    mqtt_client_id: str

    topic_update: str
    topic_status: str
    topic_log: str

    status_stale_seconds: int
    refresh_lockout_seconds: int
    log_buffer_size: int

    data_dir: Path
    render_dir: Path
    upload_dir: Path
    max_upload_bytes: int

    panel_width: int
    panel_height: int

    @classmethod
    def load(cls, env_file: Path | None = None) -> "Config":
        _load_dotenv(env_file or (ROOT / ".env"))

        host = _env("HOST", "0.0.0.0") or "0.0.0.0"
        port = _int("PORT", 5555)
        public_base_url = _normalize_base_url(_env("PUBLIC_BASE_URL"), port=port)

        data_dir = Path(_env("DATA_DIR", str(ROOT / "data")) or "data")
        if not data_dir.is_absolute():
            data_dir = (ROOT / data_dir).resolve()

        render_dir_raw = _env("RENDER_DIR")
        render_dir = Path(render_dir_raw) if render_dir_raw else data_dir / "renders"
        if not render_dir.is_absolute():
            render_dir = (ROOT / render_dir).resolve()

        upload_dir_raw = _env("UPLOAD_DIR")
        upload_dir = Path(upload_dir_raw) if upload_dir_raw else data_dir / "uploads"
        if not upload_dir.is_absolute():
            upload_dir = (ROOT / upload_dir).resolve()

        return cls(
            host=host,
            port=port,
            public_base_url=public_base_url,
            mqtt_host=_env("MQTT_HOST", "localhost") or "localhost",
            mqtt_port=_int("MQTT_PORT", 1883),
            mqtt_username=_env("MQTT_USERNAME"),
            mqtt_password=_env("MQTT_PASSWORD"),
            mqtt_client_id=_env("MQTT_CLIENT_ID", "inky-dash-companion") or "inky-dash-companion",
            topic_update=_env("MQTT_TOPIC_UPDATE", "inky/update") or "inky/update",
            topic_status=_env("MQTT_TOPIC_STATUS", "inky/status") or "inky/status",
            topic_log=_env("MQTT_TOPIC_LOG", "inky/log") or "inky/log",
            status_stale_seconds=_int("STATUS_STALE_SECONDS", 120),
            refresh_lockout_seconds=_int("REFRESH_LOCKOUT_SECONDS", 30),
            log_buffer_size=_int("LOG_BUFFER_SIZE", 50),
            data_dir=data_dir,
            render_dir=render_dir,
            upload_dir=upload_dir,
            max_upload_bytes=_int("MAX_UPLOAD_BYTES", 50 * 1024 * 1024),
            panel_width=_int("PANEL_WIDTH", 800),
            panel_height=_int("PANEL_HEIGHT", 480),
        )

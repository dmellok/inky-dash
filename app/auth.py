"""Single-shared-password gate for the admin UI + API.

Design choices and trade-offs (see also the README "Heads up" section):

* **Single password, no usernames.** Whoever opens the UI is admin.
  This matches the single-user-on-a-LAN reality of the app and skips
  multi-tenancy plumbing nobody asked for.
* **PBKDF2-HMAC-SHA256, stdlib only.** No new dependency. 600k
  iterations + 16-byte random salt + constant-time compare. Plenty for
  a hobbyist app; if you need argon2 swap it out behind ``hash_password``
  and ``verify_password``.
* **Session cookie via Flask's signed-cookie session.** The
  ``SECRET_KEY`` is generated on first boot and persisted to
  ``data/core/.secret_key`` so sessions survive restarts; the file is
  written 0600.
* **Routes:**
    - ``GET  /setup``   — first-run password creation (only available
      when no password is set)
    - ``POST /setup``   — save the new password + log in
    - ``GET  /login``   — login form (with ``?next=...`` redirect)
    - ``POST /login``   — verify password + log in
    - ``POST /logout``  — clear session
* **The gate** (a ``before_request`` hook) classifies each request:
    - Always public: ``/login``, ``/setup``, ``/healthz``, static
      assets (``/static/...``, ``/plugins/<id>/static|files/...``).
    - Public from localhost only: ``/compose/<id>`` so the Playwright
      renderer (always loopback) can keep working without a token.
    - Always public: ``/renders/<digest>.png`` so HA's image entity can
      fetch it from off-box. Digests are 16-hex SHA256; mild obscurity,
      not security. Documented in the README hobby-project disclaimer.
    - Everything else: requires the session ``authed`` flag.
* **HTML pages** that fail the gate get a 302 to ``/login?next=...``.
  **API + JSON paths** (``/api/...``) get a 401 JSON body. Keeps
  scripted clients from hitting a render-mode mismatch.

mypy --strict applies via the project config.
"""

from __future__ import annotations

import contextlib
import hmac
import logging
import os
import secrets
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from flask import (
    Blueprint,
    Flask,
    Response,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

if TYPE_CHECKING:
    from app.state.app_settings import AppSettingsStore

logger = logging.getLogger(__name__)

# PBKDF2 cost. Tweak upward when machines get faster. Existing hashes
# remain valid because the iteration count rides along in the encoded
# string.
PBKDF2_ITERS: Final[int] = 600_000
PBKDF2_HASH: Final[str] = "sha256"
PBKDF2_KEYLEN: Final[int] = 32  # 256-bit output
SALT_BYTES: Final[int] = 16
MIN_PASSWORD_LEN: Final[int] = 6

SESSION_KEY_AUTHED: Final[str] = "authed"

# URL prefixes that bypass the auth gate. ``/static/`` covers Flask's
# own static endpoint AND every Lit bundle under ``static/dist/``.
ALWAYS_PUBLIC_PREFIXES: Final[tuple[str, ...]] = (
    "/static/",
    "/healthz",
    "/login",
    "/setup",
    "/logout",
    "/favicon",
    "/renders/",  # ← documented bypass: HA image entity needs this off-box
)

# Plugin assets (CSS / JS / fonts) ship through ``/plugins/<id>/...`` and
# need to load on the login page itself (for icons). The plugin_loader
# already restricts which paths under the plugin folder are reachable.
PLUGIN_ASSET_RE_PREFIX: Final[str] = "/plugins/"

# /compose/<id> is public when the request comes from loopback so the
# Playwright renderer (always hits ``http://localhost:5555``) can keep
# screenshotting without us minting a service token. From any other host
# it's gated like the rest of the admin.
LOOPBACK_HOSTS: Final[frozenset[str]] = frozenset({"127.0.0.1", "::1", "localhost"})


# -- Password hashing --------------------------------------------------


def hash_password(password: str) -> str:
    """Return a PBKDF2-HMAC-SHA256 hash encoded as
    ``pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>``."""
    if not password:
        raise ValueError("password must not be empty")
    salt = secrets.token_bytes(SALT_BYTES)
    derived = _pbkdf2(password, salt, PBKDF2_ITERS)
    return f"pbkdf2_sha256${PBKDF2_ITERS}${salt.hex()}${derived.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    """Constant-time check of ``password`` against the stored encoding.
    Returns ``False`` (not raise) on any malformed input — a corrupted
    hash should not crash the login flow, just refuse the credential."""
    if not password or not encoded:
        return False
    try:
        scheme, iters_s, salt_hex, hash_hex = encoded.split("$", 3)
    except ValueError:
        return False
    if scheme != "pbkdf2_sha256":
        return False
    try:
        iters = int(iters_s)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except ValueError:
        return False
    if iters <= 0 or not salt or not expected:
        return False
    derived = _pbkdf2(password, salt, iters)
    return hmac.compare_digest(derived, expected)


def _pbkdf2(password: str, salt: bytes, iters: int) -> bytes:
    import hashlib

    return hashlib.pbkdf2_hmac(
        PBKDF2_HASH, password.encode("utf-8"), salt, iters, dklen=PBKDF2_KEYLEN
    )


# -- SECRET_KEY persistence -------------------------------------------


def load_or_create_secret_key(data_dir: Path) -> bytes:
    """Read ``data/core/.secret_key`` or create one. 32 random bytes —
    enough for Flask's signed-cookie session. Written 0600 so other
    users on the box can't read it."""
    path = data_dir / ".secret_key"
    if path.exists():
        try:
            raw = path.read_bytes()
            if len(raw) >= 32:
                return raw
        except OSError:
            pass
    path.parent.mkdir(parents=True, exist_ok=True)
    new_key = secrets.token_bytes(32)
    path.write_bytes(new_key)
    # Windows / FS without POSIX perms can't chmod — best effort.
    with contextlib.suppress(OSError):
        os.chmod(path, 0o600)
    return new_key


# -- Gate helpers ------------------------------------------------------


def password_is_set(settings_store: AppSettingsStore) -> bool:
    """``True`` if the stored AppSettings has a non-empty password hash."""
    return bool(settings_store.load().auth.password_hash)


def _path_is_always_public(path: str) -> bool:
    for prefix in ALWAYS_PUBLIC_PREFIXES:
        if path == prefix or path.startswith(prefix):
            return True
    # Plugin assets live under /plugins/<id>/(static|files|client.css|client.js).
    # The plugin_loader already restricts which paths resolve; we just need
    # the gate to let them through so widgets can paint on /login / /setup.
    return path.startswith(PLUGIN_ASSET_RE_PREFIX)


# -- Blueprint + gate ---------------------------------------------------


bp = Blueprint("auth", __name__)


def install_gate(app: Flask, settings_store: AppSettingsStore) -> None:
    """Wire the auth gate + login routes into ``app``.

    Call this once during ``create_app`` after the SECRET_KEY has been
    set and the AppSettingsStore is in ``app.config``.
    """
    app.register_blueprint(bp)

    @app.before_request
    def _auth_gate() -> Any:
        # Test-fixture escape hatch: the live_server_url fixture sets this
        # so Playwright-driven smoke tests can hit /compose, /_test, and
        # /api endpoints without juggling session cookies. Distinct from
        # Flask's TESTING flag so tests/test_auth.py can still exercise
        # the real gate against a normally-configured TESTING app.
        if current_app.config.get("AUTH_BYPASS_FOR_TESTS"):
            return None
        # OPTIONS bypasses — saves CORS preflight from needing a session.
        # Inky Dash isn't intended to be hit cross-origin anyway, but
        # defensive.
        if request.method == "OPTIONS":
            return None
        path = request.path or "/"
        if _path_is_always_public(path):
            return None
        # /compose/<id> is open to loopback only (Playwright renderer
        # hits ``http://localhost:5555``). Any other host gets gated.
        if path.startswith("/compose/") and (request.remote_addr or "") in LOOPBACK_HOSTS:
            return None
        wants_json = path.startswith("/api/")
        # If no password is set yet, force the user through /setup
        # before anything else loads.
        if not password_is_set(settings_store):
            if path.startswith("/setup"):
                return None
            if wants_json:
                return _unauth_json("setup required: visit /setup in a browser")
            return redirect(url_for("auth.setup_page"))
        # Password is set — check the session.
        if session.get(SESSION_KEY_AUTHED):
            return None
        if wants_json:
            return _unauth_json("authentication required")
        return redirect(url_for("auth.login_page", next=path))


def _unauth_json(message: str) -> Response:
    resp = jsonify({"error": message})
    resp.status_code = 401
    return resp


# -- Routes ------------------------------------------------------------


def _settings_store() -> AppSettingsStore:
    store: AppSettingsStore = current_app.config["APP_SETTINGS_STORE"]
    return store


# Routes return werkzeug Response (redirect()/jsonify()) OR a str
# (render_template()) OR a (str, int) tuple. ``Any`` is the honest
# signature for the union of Flask-accepted return types.
@bp.get("/setup")
def setup_page() -> Any:
    if password_is_set(_settings_store()):
        # Already set — kick to /login if not authed, or home.
        if session.get(SESSION_KEY_AUTHED):
            return redirect(url_for("index"))
        return redirect(url_for("auth.login_page"))
    return render_template("setup.html", error=None, min_length=MIN_PASSWORD_LEN)


@bp.post("/setup")
def setup_submit() -> Any:
    if password_is_set(_settings_store()):
        return redirect(url_for("auth.login_page"))
    password = (request.form.get("password") or "").strip()
    confirm = (request.form.get("confirm") or "").strip()
    err = _validate_new_password(password, confirm)
    if err:
        return render_template("setup.html", error=err, min_length=MIN_PASSWORD_LEN)
    store = _settings_store()
    settings = store.load()
    settings.auth.password_hash = hash_password(password)
    store.save(settings)
    logger.info("auth: first-run password set")
    session[SESSION_KEY_AUTHED] = True
    session.permanent = True
    return redirect(url_for("index"))


@bp.get("/login")
def login_page() -> Any:
    if not password_is_set(_settings_store()):
        return redirect(url_for("auth.setup_page"))
    if session.get(SESSION_KEY_AUTHED):
        return redirect(_safe_next(request.args.get("next")) or url_for("index"))
    return render_template(
        "login.html",
        error=None,
        next_url=request.args.get("next") or "",
    )


@bp.post("/login")
def login_submit() -> Any:
    if not password_is_set(_settings_store()):
        return redirect(url_for("auth.setup_page"))
    password = (request.form.get("password") or "").strip()
    nxt = request.form.get("next") or ""
    settings = _settings_store().load()
    if not verify_password(password, settings.auth.password_hash):
        # Brief, deliberate delay would help against online brute force,
        # but for a LAN tool it's overkill — the WiFi is the real gate.
        return (
            render_template("login.html", error="Wrong password.", next_url=nxt),
            401,
        )
    session.clear()
    session[SESSION_KEY_AUTHED] = True
    session.permanent = True
    return redirect(_safe_next(nxt) or url_for("index"))


@bp.post("/logout")
def logout_submit() -> Any:
    session.clear()
    return redirect(url_for("auth.login_page"))


@bp.post("/api/auth/change-password")
def change_password() -> Any:
    """Authenticated re-key. Verifies the current password then stores
    the new one. Used by the Settings page."""
    if not session.get(SESSION_KEY_AUTHED):
        return _unauth_json("authentication required"), 401
    body = request.get_json(silent=True) or {}
    current = (body.get("current") or "").strip()
    new = (body.get("new") or "").strip()
    confirm = (body.get("confirm") or "").strip()
    store = _settings_store()
    settings = store.load()
    if not verify_password(current, settings.auth.password_hash):
        return jsonify({"error": "Current password is wrong."}), 400
    err = _validate_new_password(new, confirm)
    if err:
        return jsonify({"error": err}), 400
    settings.auth.password_hash = hash_password(new)
    store.save(settings)
    logger.info("auth: password changed")
    return jsonify({"ok": True})


# -- Internal helpers --------------------------------------------------


def _validate_new_password(password: str, confirm: str) -> str | None:
    if not password:
        return "Password is required."
    if len(password) < MIN_PASSWORD_LEN:
        return f"Password must be at least {MIN_PASSWORD_LEN} characters."
    if password != confirm:
        return "Passwords don't match."
    return None


def _safe_next(value: str | None) -> str | None:
    """Refuse external-redirect targets — only allow relative paths
    inside the app. Prevents an open-redirect via ?next=https://evil/."""
    if not value:
        return None
    if not value.startswith("/") or value.startswith("//"):
        return None
    return value


# -- Test helper -------------------------------------------------------


def mask_auth(settings_dump: dict[str, object]) -> dict[str, object]:
    """Replace ``auth.password_hash`` with a presence marker so the
    real hash never crosses the wire. Used by the /api/app/settings
    response masker, paired with the existing MQTT password masker."""
    auth = settings_dump.get("auth")
    if isinstance(auth, dict):
        # Only emit whether a password is set, never the hash itself.
        has = bool(auth.get("password_hash"))
        settings_dump["auth"] = {"password_set": has}
    return settings_dump

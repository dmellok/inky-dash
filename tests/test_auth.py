"""Tests for the single-shared-password auth gate (app/auth.py).

Covers the password hash + verify primitives, the setup / login flows,
and the before_request gate's classification:
- public paths (/login, /setup, /healthz, /static/, /renders/, /plugins/)
- loopback-only /compose/<id> (Playwright renderer needs this)
- HTML routes that 302 to /login when unauthed
- /api/ routes that 401 JSON when unauthed
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app import create_app
from app.auth import (
    hash_password,
    load_or_create_secret_key,
    verify_password,
)

from ._helpers import FakeBridge
from .conftest import TEST_PASSWORD

# -- Hash + verify -----------------------------------------------------


def test_hash_password_returns_encoded_string() -> None:
    encoded = hash_password("hunter22")
    parts = encoded.split("$")
    assert len(parts) == 4
    assert parts[0] == "pbkdf2_sha256"
    assert int(parts[1]) > 0  # iterations
    assert len(parts[2]) == 32  # salt hex (16 bytes)
    assert len(parts[3]) == 64  # hash hex (32 bytes)


def test_verify_round_trips() -> None:
    encoded = hash_password("the right one")
    assert verify_password("the right one", encoded) is True
    assert verify_password("the wrong one", encoded) is False
    assert verify_password("", encoded) is False


def test_verify_refuses_malformed_encoding() -> None:
    assert verify_password("x", "") is False
    assert verify_password("x", "not-a-hash") is False
    assert verify_password("x", "pbkdf2_sha256$0$$") is False
    assert verify_password("x", "pbkdf2_sha512$1$ab$cd") is False  # wrong scheme


def test_hash_empty_password_raises() -> None:
    with pytest.raises(ValueError):
        hash_password("")


def test_hash_uses_fresh_salt_each_time() -> None:
    a = hash_password("same")
    b = hash_password("same")
    assert a != b, "salt should differ each call"
    assert verify_password("same", a)
    assert verify_password("same", b)


# -- SECRET_KEY persistence -------------------------------------------


def test_secret_key_persists_across_calls(tmp_path: Path) -> None:
    first = load_or_create_secret_key(tmp_path)
    second = load_or_create_secret_key(tmp_path)
    assert first == second
    assert len(first) >= 32
    assert (tmp_path / ".secret_key").exists()


def test_secret_key_regenerates_when_too_short(tmp_path: Path) -> None:
    (tmp_path / ".secret_key").write_bytes(b"tiny")
    key = load_or_create_secret_key(tmp_path)
    assert len(key) >= 32


# -- First-run setup flow ---------------------------------------------


def _fresh_app(tmp_path: Path) -> Flask:
    """Build an app with NO password set — for testing the /setup flow."""
    app = create_app(data_root=tmp_path / "data", bridge=FakeBridge(), start_scheduler=False)
    app.config["TESTING"] = True
    return app


def test_setup_page_redirects_to_login_when_password_already_set(
    unauth_client: FlaskClient,
) -> None:
    res = unauth_client.get("/setup")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]


def test_setup_flow_with_fresh_install(tmp_path: Path) -> None:
    app = _fresh_app(tmp_path)
    client = app.test_client()
    # /setup is reachable; everything else redirects to it.
    assert client.get("/setup").status_code == 200
    assert client.get("/").status_code == 302
    assert "/setup" in client.get("/").headers["Location"]
    # Submit a valid password.
    res = client.post("/setup", data={"password": "new-password", "confirm": "new-password"})
    assert res.status_code == 302
    # Now logged in — index returns 200.
    assert client.get("/").status_code == 200


def test_setup_rejects_short_password(tmp_path: Path) -> None:
    app = _fresh_app(tmp_path)
    client = app.test_client()
    res = client.post("/setup", data={"password": "abc", "confirm": "abc"})
    assert res.status_code == 200
    assert b"at least" in res.data


def test_setup_rejects_mismatched_confirm(tmp_path: Path) -> None:
    app = _fresh_app(tmp_path)
    client = app.test_client()
    res = client.post("/setup", data={"password": "longenough", "confirm": "different"})
    assert res.status_code == 200
    assert b"don" in res.data and b"match" in res.data


# -- Login flow --------------------------------------------------------


def test_login_with_right_password(unauth_client: FlaskClient) -> None:
    res = unauth_client.post("/login", data={"password": TEST_PASSWORD}, follow_redirects=False)
    assert res.status_code == 302
    # Subsequent request without explicit cookie still hits the session.
    assert unauth_client.get("/").status_code == 200


def test_login_with_wrong_password(unauth_client: FlaskClient) -> None:
    res = unauth_client.post("/login", data={"password": "nope"})
    assert res.status_code == 401
    # Still not authed.
    assert unauth_client.get("/").status_code == 302
    assert "/login" in unauth_client.get("/").headers["Location"]


def test_login_next_param_is_preserved(unauth_client: FlaskClient) -> None:
    res = unauth_client.post(
        "/login",
        data={"password": TEST_PASSWORD, "next": "/settings"},
        follow_redirects=False,
    )
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/settings")


def test_login_refuses_external_next_redirect(unauth_client: FlaskClient) -> None:
    """The ?next= sanitiser blocks open redirects to other origins."""
    res = unauth_client.post(
        "/login",
        data={"password": TEST_PASSWORD, "next": "https://evil.example.com/x"},
        follow_redirects=False,
    )
    assert res.status_code == 302
    # Should NOT land on the external URL.
    assert "evil.example.com" not in res.headers["Location"]


def test_logout_clears_session(client: FlaskClient) -> None:
    # client is pre-authed by the fixture.
    assert client.get("/").status_code == 200
    res = client.post("/logout")
    assert res.status_code == 302
    # Now unauthed.
    assert client.get("/").status_code == 302
    assert "/login" in client.get("/").headers["Location"]


# -- The auth gate -----------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/login",
        "/healthz",
        "/static/icons/phosphor.css",
        # Plugin assets need to be reachable on /login (icons, fonts).
        "/plugins/example_minimal/client.js",
    ],
)
def test_public_paths_dont_redirect_to_login(unauth_client: FlaskClient, path: str) -> None:
    res = unauth_client.get(path)
    # 200 / 404 are both fine — we just don't want a 302 with /login in
    # the Location, which would mean the gate misclassified the path.
    if res.status_code == 302:
        assert "/login" not in (res.headers.get("Location") or ""), (
            f"{path} got bounced to /login (status 302)"
        )


def test_renders_path_open_to_any_host(unauth_client: FlaskClient) -> None:
    """HA's image entity fetches /renders/<digest>.png from off-box —
    the gate must let it through. Digest doesn't exist, so we expect
    404, NOT 302."""
    res = unauth_client.get("/renders/0123456789abcdef.png")
    assert res.status_code == 404


def test_api_routes_return_401_json_when_unauthed(
    unauth_client: FlaskClient,
) -> None:
    res = unauth_client.get("/api/app/settings")
    assert res.status_code == 401
    body = res.get_json()
    assert body is not None and "error" in body


def test_html_routes_redirect_to_login_when_unauthed(
    unauth_client: FlaskClient,
) -> None:
    res = unauth_client.get("/settings")
    assert res.status_code == 302
    assert "/login" in res.headers["Location"]
    # next= is preserved for post-login redirect.
    assert "next=" in res.headers["Location"]


def test_compose_open_to_loopback(unauth_client: FlaskClient) -> None:
    """Playwright hits /compose/<id> from localhost. The gate is
    expected to let loopback through even without a session, otherwise
    the renderer can't screenshot."""
    # The Flask test client reports remote_addr=127.0.0.1 by default,
    # which matches the LOOPBACK_HOSTS allowlist.
    res = unauth_client.get("/compose/welcome")
    # The page may 200 (welcome dashboard auto-created) or 404 (missing
    # page), but it must NOT 302 to /login.
    assert res.status_code != 302


# -- /api/app/settings masks the hash ----------------------------------


def test_get_settings_masks_password_hash(client: FlaskClient) -> None:
    res = client.get("/api/app/settings")
    assert res.status_code == 200
    body = res.get_json()
    auth_block = body.get("auth", {})
    assert "password_hash" not in auth_block, "hash leaked to client"
    assert auth_block == {"password_set": True}


def test_put_settings_does_not_clear_password(client: FlaskClient) -> None:
    """PUT roundtripping the masked GET shape (auth.password_set=True)
    must not wipe the real hash on the server."""
    # Send a put that includes the masked auth block exactly as the GET
    # would have returned it.
    res = client.put(
        "/api/app/settings",
        json={"auth": {"password_set": True}, "base_url": "http://x:5555"},
    )
    assert res.status_code == 200
    # Verify by trying to log in with the original password — still works.
    client.post("/logout")
    res = client.post("/login", data={"password": TEST_PASSWORD})
    assert res.status_code == 302  # success redirect


# -- Change-password API ----------------------------------------------


def test_change_password_round_trip(client: FlaskClient) -> None:
    res = client.post(
        "/api/auth/change-password",
        json={
            "current": TEST_PASSWORD,
            "new": "brand-new-pw-9876",
            "confirm": "brand-new-pw-9876",
        },
    )
    assert res.status_code == 200
    assert res.get_json() == {"ok": True}
    # Old password no longer works.
    client.post("/logout")
    bad = client.post("/login", data={"password": TEST_PASSWORD})
    assert bad.status_code == 401
    good = client.post("/login", data={"password": "brand-new-pw-9876"})
    assert good.status_code == 302


def test_change_password_rejects_wrong_current(client: FlaskClient) -> None:
    res = client.post(
        "/api/auth/change-password",
        json={
            "current": "wrong",
            "new": "newpassword",
            "confirm": "newpassword",
        },
    )
    assert res.status_code == 400
    assert "wrong" in res.get_json()["error"].lower()


def test_change_password_rejects_mismatch(client: FlaskClient) -> None:
    res = client.post(
        "/api/auth/change-password",
        json={
            "current": TEST_PASSWORD,
            "new": "newpassword",
            "confirm": "different",
        },
    )
    assert res.status_code == 400


def test_change_password_requires_session(unauth_client: FlaskClient) -> None:
    res = unauth_client.post(
        "/api/auth/change-password",
        json={
            "current": TEST_PASSWORD,
            "new": "newpassword",
            "confirm": "newpassword",
        },
    )
    assert res.status_code == 401

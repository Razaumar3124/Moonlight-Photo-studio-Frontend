"""Phase 2 security regression tests.

Covers spoofed client IPs, brute force, OTP abuse, refresh-token reuse and concurrency, CSRF,
oversized uploads, authorization of revoked tokens, information leakage, health exposure,
security headers and logging.
"""

import asyncio
import json
import logging
import time
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi.security import HTTPAuthorizationCredentials
from httpx import AsyncClient

from app.api.dependencies import (
    get_current_user,
    get_optional_current_user,
    get_settings,
    get_template_service,
)
from app.core.exceptions import TokenRevokedException
from app.core.logging import JSONFormatter
from app.core.security import (
    _dummy_password_hash,
    create_access_token,
    get_client_ip,
    hash_password,
)
from app.services.email_service import EmailDeliveryException, email_service
from app.services.rate_limiter import MemoryRateLimitStore, _storage_key, rate_limiter
from tests.fakes import FakeR2Storage, FakeSessionRepository, FakeUserRepository
from tests.test_image_processing import make_test_image
from tests.test_photo_upload import register_test_user
from tests.test_quote_prepare import make_valid_design_payload

API = "/api/v1"
PASSWORD = "CorrectHorse123"


# --------------------------------------------------------------------------- helpers


@pytest.fixture
def settings_env(monkeypatch: pytest.MonkeyPatch, app):
    """Override settings for one test via env vars (affects get_settings() and SettingsDep)."""

    def apply(**values):
        for key, value in values.items():
            monkeypatch.setenv(key, str(value))
        get_settings.cache_clear()
        fresh = get_settings()
        app.dependency_overrides[get_settings] = lambda: fresh
        return fresh

    yield apply
    monkeypatch.undo()
    get_settings.cache_clear()


async def _register(client: AsyncClient, email: str, phone: str) -> dict:
    res = await client.post(
        f"{API}/auth/register",
        json={"full_name": "Sec Tester", "email": email, "phone": phone, "password": PASSWORD},
    )
    assert res.status_code == 201, res.text
    return {"body": res.json(), "refresh": res.cookies["refresh_token"]}


def _login(client: AsyncClient, identifier: str, password: str, **headers):
    return client.post(
        f"{API}/auth/login",
        json={"identifier": identifier, "password": password},
        headers=headers or None,
    )


def _refresh(client: AsyncClient, raw_token: str):
    client.cookies.clear()
    return client.post(f"{API}/auth/refresh", headers={"Cookie": f"refresh_token={raw_token}"})


def _request(peer: str, headers: dict | None = None) -> SimpleNamespace:
    return SimpleNamespace(client=SimpleNamespace(host=peer), headers=headers or {})


# ------------------------------------------------------------------- 1. client IP


def test_forwarding_headers_ignored_without_trusted_proxies():
    req = _request(
        "198.51.100.7",
        {"x-forwarded-for": "1.2.3.4", "x-real-ip": "5.6.7.8", "cf-connecting-ip": "9.9.9.9"},
    )
    assert get_client_ip(req) == "198.51.100.7"


@pytest.mark.parametrize(
    ("peer", "headers", "expected"),
    [
        # Trusted proxy appended the real client; a client-prepended value is ignored.
        ("10.0.0.9", {"x-forwarded-for": "6.6.6.6, 203.0.113.5"}, "203.0.113.5"),
        # Multiple trusted hops are skipped right to left.
        ("10.0.0.9", {"x-forwarded-for": "203.0.113.5, 10.0.0.4"}, "203.0.113.5"),
        # X-Real-IP only when there is no X-Forwarded-For.
        ("10.0.0.9", {"x-real-ip": "203.0.113.6"}, "203.0.113.6"),
        # A malformed hop stops the walk at the last valid address.
        ("10.0.0.9", {"x-forwarded-for": "203.0.113.5, not-an-ip, 10.0.0.4"}, "10.0.0.4"),
        # CF-Connecting-IP alone is never trusted.
        ("10.0.0.9", {"cf-connecting-ip": "9.9.9.9"}, "10.0.0.9"),
        # Untrusted peer: its headers are ignored.
        ("198.51.100.7", {"x-forwarded-for": "203.0.113.5"}, "198.51.100.7"),
    ],
)
def test_trusted_proxy_resolution(settings_env, peer, headers, expected):
    settings_env(TRUSTED_PROXIES="10.0.0.0/8")
    assert get_client_ip(_request(peer, headers)) == expected


async def test_spoofed_forwarded_for_cannot_bypass_login_lockout(client: AsyncClient):
    await _register(client, "spoof@example.com", "+919800000001")
    for attempt in range(5):
        res = await _login(
            client, "spoof@example.com", "WrongPass1", **{"X-Forwarded-For": f"7.7.7.{attempt}"}
        )
        assert res.status_code == 401
    res = await _login(client, "spoof@example.com", "WrongPass1", **{"X-Forwarded-For": "8.8.8.8"})
    assert res.status_code == 429


# ------------------------------------------------------------------ 2. brute force


async def test_login_lockout_returns_retry_after(client: AsyncClient):
    await _register(client, "brute@example.com", "+919800000002")
    for _ in range(5):
        assert (await _login(client, "brute@example.com", "WrongPass1")).status_code == 401

    blocked = await _login(client, "brute@example.com", PASSWORD)  # even the right password
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert 1 <= int(blocked.headers["retry-after"]) <= 300


async def test_distributed_guessing_hits_per_account_limit(client: AsyncClient, settings_env):
    settings_env(TRUSTED_PROXIES="127.0.0.1")
    await _register(client, "distributed@example.com", "+919800000003")
    for i in range(20):
        res = await _login(
            client, "distributed@example.com", "WrongPass1", **{"X-Forwarded-For": f"203.0.113.{i}"}
        )
        assert res.status_code == 401, i
    res = await _login(
        client, "distributed@example.com", "WrongPass1", **{"X-Forwarded-For": "203.0.113.99"}
    )
    assert res.status_code == 429


async def test_credential_spraying_hits_per_ip_limit(client: AsyncClient):
    for i in range(30):
        res = await _login(client, f"nobody{i}@example.com", "WrongPass1")
        assert res.status_code == 401, i
    assert (await _login(client, "another@example.com", "WrongPass1")).status_code == 429


async def test_trusted_proxy_isolates_clients(client: AsyncClient, settings_env):
    settings_env(TRUSTED_PROXIES="127.0.0.1")
    await _register(client, "isolated@example.com", "+919800000004")
    for _ in range(5):
        await _login(client, "isolated@example.com", "Wrong1", **{"X-Forwarded-For": "203.0.113.1"})
    other = await _login(
        client, "isolated@example.com", PASSWORD, **{"X-Forwarded-For": "203.0.113.2"}
    )
    assert other.status_code == 200


async def test_successful_login_resets_account_counter_not_ip_counter(client: AsyncClient):
    await _register(client, "reset@example.com", "+919800000005")
    for _ in range(4):
        await _login(client, "reset@example.com", "WrongPass1")
    assert (await _login(client, "reset@example.com", PASSWORD)).status_code == 200
    for _ in range(5):  # a fresh allowance of 5 after the success
        assert (await _login(client, "reset@example.com", "WrongPass1")).status_code == 401
    count, _ = await rate_limiter.memory.hit(_storage_key("login:ip", "127.0.0.1"), 300)
    assert count == 4 + 1 + 5 + 1  # the IP counter kept counting throughout


def test_dummy_hash_is_a_real_argon2id_hash_with_production_parameters():
    from argon2 import extract_parameters

    dummy = _dummy_password_hash()
    real = hash_password("x")
    assert dummy.startswith("$argon2id$")
    assert extract_parameters(dummy) == extract_parameters(real)
    with pytest.raises(VerifyMismatchError):  # a genuine verify (the old one raised instantly)
        PasswordHasher().verify(dummy, "anything")


async def test_unknown_account_costs_as_much_as_a_wrong_password(client: AsyncClient):
    await _register(client, "timing@example.com", "+919800000006")

    async def median_ms(identifier: str) -> float:
        samples = []
        for _ in range(3):
            rate_limiter.clear_all()
            start = time.perf_counter()
            await _login(client, identifier, "WrongPass1")
            samples.append((time.perf_counter() - start) * 1000)
        return sorted(samples)[1]

    known = await median_ms("timing@example.com")
    unknown = await median_ms("ghost@example.com")
    # Before the fix the unknown path skipped Argon2 entirely (~0 ms vs tens of ms).
    assert unknown > known * 0.4, (unknown, known)


# -------------------------------------------------------------------- 3. OTP abuse


async def test_otp_verification_limited_per_email_across_codes(client: AsyncClient):
    for _ in range(10):
        res = await client.post(
            f"{API}/auth/forgot-password/verify",
            json={"email": "victim@example.com", "otp": "123456"},
        )
        assert res.status_code == 422
    res = await client.post(
        f"{API}/auth/forgot-password/verify", json={"email": "victim@example.com", "otp": "654321"}
    )
    assert res.status_code == 429


async def test_otp_requests_limited_per_email(client: AsyncClient):
    for _ in range(3):
        res = await client.post(f"{API}/auth/forgot-password", json={"email": "flood@example.com"})
        assert res.status_code == 200
    res = await client.post(f"{API}/auth/forgot-password", json={"email": "flood@example.com"})
    assert res.status_code == 429


async def test_forgot_password_is_identical_even_when_email_delivery_fails(client: AsyncClient):
    await _register(client, "exists@example.com", "+919800000007")
    failing = AsyncMock(
        side_effect=EmailDeliveryException(message="boom", issue="Resend 403 test mode")
    )
    with patch.object(email_service, "send_otp_email", failing):
        existing = await client.post(
            f"{API}/auth/forgot-password", json={"email": "exists@example.com"}
        )
    missing = await client.post(
        f"{API}/auth/forgot-password", json={"email": "missing@example.com"}
    )

    assert existing.status_code == missing.status_code == 200
    assert existing.json() == missing.json()
    failing.assert_awaited_once()  # delivery ran (in the background) and its error was swallowed


async def test_password_reset_step_is_rate_limited(client: AsyncClient):
    for _ in range(10):
        res = await client.post(
            f"{API}/auth/forgot-password/reset",
            json={"reset_token": "rst_" + "x" * 40, "new_password": "NewPassword123"},
        )
        assert res.status_code == 401
    res = await client.post(
        f"{API}/auth/forgot-password/reset",
        json={"reset_token": "rst_" + "x" * 40, "new_password": "NewPassword123"},
    )
    assert res.status_code == 429


# ---------------------------------------------------------- 4. refresh-token safety


async def test_refresh_token_never_accepted_from_body(client: AsyncClient):
    session = await _register(client, "bodyless@example.com", "+919800000008")
    client.cookies.clear()
    res = await client.post(f"{API}/auth/refresh", json={"refresh_token": session["refresh"]})
    assert res.status_code == 401


async def test_concurrent_refreshes_rotate_once_and_keep_the_session(
    client: AsyncClient, fake_session_repo: FakeSessionRepository
):
    session = await _register(client, "tabs@example.com", "+919800000009")
    responses = await asyncio.gather(*(_refresh(client, session["refresh"]) for _ in range(5)))

    assert [r.status_code for r in responses] == [200] * 5
    assert all(r.json()["access_token"] for r in responses)
    rotated = [r for r in responses if "refresh_token" in r.headers.get("set-cookie", "")]
    assert len(rotated) == 1  # exactly one winner rotated the cookie
    active = [d for d in fake_session_repo.refresh_tokens.values() if not d["is_revoked"]]
    assert len(active) == 1 and active[0]["revoked_reason"] is None


async def test_replay_after_grace_window_revokes_the_whole_family(
    client: AsyncClient, fake_session_repo: FakeSessionRepository
):
    session = await _register(client, "thief@example.com", "+919800000010")
    first = await _refresh(client, session["refresh"])
    successor = first.cookies["refresh_token"]

    for doc in fake_session_repo.refresh_tokens.values():  # age the rotation past the grace
        if doc["revoked_reason"] == "rotated":
            doc["revoked_at"] = datetime.now(UTC) - timedelta(seconds=120)

    replay = await _refresh(client, session["refresh"])
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "TOKEN_REVOKED"
    assert (await _refresh(client, successor)).status_code == 401  # family is gone
    assert all(d["is_revoked"] for d in fake_session_repo.refresh_tokens.values())


async def test_logged_out_token_cannot_refresh(client: AsyncClient):
    session = await _register(client, "logout@example.com", "+919800000011")
    client.cookies.clear()
    out = await client.post(
        f"{API}/auth/logout", headers={"Cookie": f"refresh_token={session['refresh']}"}
    )
    assert out.status_code == 204
    assert "refresh_token=" in out.headers["set-cookie"]  # cookie cleared
    assert (await _refresh(client, session["refresh"])).status_code == 401


async def test_refresh_cookie_path_is_configurable(client: AsyncClient, settings_env):
    settings_env(REFRESH_COOKIE_PATH="/custom/auth")
    res = await client.post(
        f"{API}/auth/register",
        json={
            "full_name": "Path Tester",
            "email": "path@example.com",
            "phone": "+919800000012",
            "password": PASSWORD,
        },
    )
    assert "path=/custom/auth" in res.headers["set-cookie"].lower()


# ------------------------------------------------- 5. token revocation & authorization


async def test_password_change_revokes_older_tokens_everywhere(fake_user_repo: FakeUserRepository):
    from app.models.user import UserInDB

    now = datetime.now(UTC)
    user = await fake_user_repo.create(
        UserInDB(
            _id="672cf1a9e4b0123456789abd",
            email="rotate@example.com",
            phone="+919800000013",
            password_hash=hash_password(PASSWORD),
            full_name="Rotate",
            created_at=now,
            updated_at=now,
        )
    )
    before, _ = create_access_token(subject=user.id)
    await fake_user_repo.update_password(user.id, hash_password("NewPassword1"))
    after, _ = create_access_token(subject=user.id)  # same second as the change

    def creds(token: str) -> HTTPAuthorizationCredentials:
        return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with pytest.raises(TokenRevokedException):
        await get_current_user(creds(before), fake_user_repo)
    # Optional-auth endpoints (photo media, geometry) used to accept the old token.
    assert await get_optional_current_user(creds(before), fake_user_repo) is None
    # Sub-second iat: a token issued right after the change is valid.
    assert (await get_current_user(creds(after), fake_user_repo)).id == user.id


async def test_unsigned_and_foreign_tokens_are_rejected(client: AsyncClient):
    none_alg = jwt.encode({"sub": "x", "iat": 1, "exp": 9999999999}, None, algorithm="none")
    forged = jwt.encode({"sub": "x", "iat": 1, "exp": 9999999999}, "x" * 40, algorithm="HS256")
    for token in (none_alg, forged):
        res = await client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 401


async def test_cross_user_access_is_denied(client: AsyncClient):
    _, owner_token = await register_test_user(client, "owner.sec@example.com")
    _, other_token = await register_test_user(client, "other.sec@example.com")
    created = await client.post(
        f"{API}/designs",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"title": "Private wall"},
    )
    design_id = created.json()["id"]
    for method in ("get", "delete"):
        res = await getattr(client, method)(
            f"{API}/designs/{design_id}", headers={"Authorization": f"Bearer {other_token}"}
        )
        assert res.status_code in (403, 404)
        assert "Private wall" not in res.text


# ------------------------------------------------------------------------- 6. CSRF


@pytest.mark.parametrize(
    "path", ["/auth/login", "/auth/register", "/auth/refresh", "/auth/logout", "/auth/google"]
)
async def test_cookie_endpoints_require_csrf_header(raw_client: AsyncClient, path: str):
    res = await raw_client.post(f"{API}{path}", json={})
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "CSRF_VALIDATION_FAILED"


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        ({"Origin": "https://evil.example"}, 403),
        ({"Origin": "null"}, 403),
        ({"Referer": "https://evil.example/page"}, 403),
        ({"Origin": "http://localhost:5173"}, 401),  # allowed frontend: reaches the handler
        ({"Referer": "http://localhost:5173/login"}, 401),
    ],
)
async def test_csrf_origin_check(client: AsyncClient, headers: dict, expected: int):
    res = await _login(client, "nobody@example.com", "WrongPass1", **headers)
    assert res.status_code == expected


async def test_cors_preflight_only_for_allowed_origins(raw_client: AsyncClient):
    preflight = {
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,x-csrf-protection",
    }
    evil = await raw_client.options(
        f"{API}/auth/refresh", headers={**preflight, "Origin": "https://evil.example"}
    )
    good = await raw_client.options(
        f"{API}/auth/refresh", headers={**preflight, "Origin": "http://localhost:5173"}
    )
    assert "access-control-allow-origin" not in evil.headers
    assert good.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "x-csrf-protection" in good.headers["access-control-allow-headers"].lower()


# --------------------------------------------------------------- 7. oversized bodies


async def test_declared_oversized_json_body_rejected_before_parsing(client: AsyncClient):
    body = json.dumps({"identifier": "a@example.com", "password": "x" * (2 * 1024 * 1024)})
    res = await client.post(
        f"{API}/auth/login", content=body, headers={"Content-Type": "application/json"}
    )
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


async def test_streamed_oversized_body_rejected(client: AsyncClient):
    async def chunks():
        for _ in range(40):
            yield b"x" * 65536  # 2.5 MB, no Content-Length

    res = await client.post(
        f"{API}/auth/login", content=chunks(), headers={"Content-Type": "application/json"}
    )
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


async def test_oversized_photo_rejected_at_both_layers(client: AsyncClient, settings_env):
    settings_env(R2_MAX_UPLOAD_MB=1)
    _, token = await register_test_user(client, "big.photo@example.com")
    auth = {"Authorization": f"Bearer {token}"}

    huge = await client.post(
        f"{API}/photos/upload", headers=auth, files={"file": ("a.jpg", b"\xff" * 1_500_000)}
    )
    just_over = await client.post(
        f"{API}/photos/upload",
        headers=auth,
        files={"file": ("b.jpg", b"\xff" * (1024 * 1024 + 20_000))},
    )
    assert huge.status_code == 413  # streaming guard (whole body over the limit)
    assert just_over.status_code == 413  # endpoint check (file over 1 MB, body under cap)
    assert just_over.json()["error"]["details"][0]["field"] == "file"


async def test_oversized_quote_preview_rejected(client: AsyncClient, settings_env):
    settings_env(QUOTE_PREVIEW_MAX_MB=1)
    _, token = await register_test_user(client, "big.quote@example.com")
    res = await client.post(
        f"{API}/quotes/prepare",
        headers={"Authorization": f"Bearer {token}"},
        data={"design_data": json.dumps(make_valid_design_payload())},
        files={"file": ("p.png", b"\x89PNG" + b"0" * (1024 * 1024 + 20_000), "image/png")},
    )
    assert res.status_code == 413


# ----------------------------------------------------------- 8. information leakage


async def test_storage_failure_does_not_leak_sdk_details(
    client: AsyncClient, fake_r2_storage: FakeR2Storage
):
    _, token = await register_test_user(client, "leak.storage@example.com")
    fake_r2_storage.should_fail_upload = True
    res = await client.post(
        f"{API}/photos/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("ok.jpg", make_test_image(600, 600, fmt="JPEG"), "image/jpeg")},
    )
    assert res.status_code == 503
    assert "Simulated" not in res.text and "R2" not in res.json()["error"]["details"][0]["issue"]


async def test_unhandled_errors_are_generic(app, client: AsyncClient):
    def boom():
        raise RuntimeError("internal-secret-123 mongodb://admin:pw@db")

    app.dependency_overrides[get_template_service] = boom
    res = await client.get(f"{API}/templates")
    assert res.status_code == 500
    assert "internal-secret" not in res.text and "mongodb" not in res.text


async def test_quote_validation_errors_do_not_echo_input(client: AsyncClient):
    _, token = await register_test_user(client, "leak.quote@example.com")
    payload = make_valid_design_payload()
    payload["wall"]["widthIn"] = "SECRET-VALUE-42"
    res = await client.post(
        f"{API}/quotes/prepare",
        headers={"Authorization": f"Bearer {token}"},
        data={"design_data": json.dumps(payload)},
        files={"file": ("p.png", make_test_image(400, 300, fmt="PNG"), "image/png")},
    )
    assert res.status_code == 422
    assert "SECRET-VALUE-42" not in res.text
    assert res.json()["error"]["details"][0]["field"] == "design_data.wall.widthIn"


def test_json_logs_are_valid_and_masked():
    record = logging.LogRecord(
        "t", logging.ERROR, __file__, 1, "connect %s", ("mongodb://admin:pw@h/x",), None
    )
    try:
        raise RuntimeError("mongodb://user:secret@host/db")
    except RuntimeError:
        import sys

        record.exc_info = sys.exc_info()
    record.request_id = "req-1"
    data = json.loads(JSONFormatter().format(record))  # used to raise TypeError
    text = json.dumps(data)
    assert data["request_id"] == "req-1"
    assert "secret" not in text and ":pw@" not in text and "args" not in data


# ---------------------------------------------------------------- 9. health exposure


async def test_detailed_health_hidden_outside_development(app, client: AsyncClient):
    from app.schemas.health import GoogleAuthHealthStatus

    staging = get_settings().model_copy(
        update={"ENVIRONMENT": "staging", "HEALTH_DIAGNOSTICS_TOKEN": "t" * 24}
    )
    app.dependency_overrides[get_settings] = lambda: staging
    google = GoogleAuthHealthStatus(status="ready", client_id_configured=True, certs_reachable=True)

    anonymous = await client.get(f"{API}/health")
    wrong = await client.get(f"{API}/health", headers={"X-Health-Token": "nope"})
    with (
        patch("app.api.v1.endpoints.health._check_google_oauth", AsyncMock(return_value=google)),
        patch("app.db.mongodb.mongo_manager.ping", AsyncMock(return_value=1.0)),
    ):
        operator = await client.get(f"{API}/health", headers={"X-Health-Token": "t" * 24})

    assert anonymous.status_code == wrong.status_code == 404
    assert operator.status_code == 200 and "components" in operator.json()


# --------------------------------------------------------------- 10. response headers


async def test_security_headers_on_api_responses(client: AsyncClient):
    res = await client.get(f"{API}/health/live")
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "DENY"
    assert res.headers["content-security-policy"].startswith("default-src 'none'")
    assert "strict-transport-security" not in res.headers  # production only

    me = await client.get(f"{API}/auth/me")
    assert me.headers["cache-control"] == "no-store"


async def test_shared_report_has_its_own_strict_headers(client: AsyncClient):
    _, token = await register_test_user(client, "report.headers@example.com")
    prepared = await client.post(
        f"{API}/quotes/prepare",
        headers={"Authorization": f"Bearer {token}"},
        data={"design_data": json.dumps(make_valid_design_payload())},
        files={"file": ("p.png", make_test_image(400, 300, fmt="PNG"), "image/png")},
    )
    assert prepared.status_code == 201, prepared.text
    path = "/api/v1/quotes/share/" + prepared.json()["report_url"].rsplit("/q/", 1)[1]
    report = await client.get(path, follow_redirects=True, headers={"Accept": "text/html"})

    assert report.status_code == 200
    assert report.headers["referrer-policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in report.headers["content-security-policy"]
    assert "script-src" not in report.headers["content-security-policy"]  # no scripts at all
    assert report.headers["cache-control"] == "private, no-store"


# --------------------------------------------------------------- 11. limiter itself


async def test_memory_rate_limit_store_is_bounded():
    store = MemoryRateLimitStore(max_keys=100)
    for i in range(1000):
        await store.hit(f"k{i}", 60)
    assert len(store) <= 100


async def test_memory_rate_limit_window_expires():
    store = MemoryRateLimitStore()
    assert (await store.hit("k", 1))[0] == 1
    assert (await store.hit("k", 1))[0] == 2
    await asyncio.sleep(1.05)
    assert (await store.hit("k", 1))[0] == 1


def test_rate_limit_keys_do_not_store_identifiers():
    key = _storage_key("login:identifier", "Person@Example.com")
    assert "person" not in key.lower() and key.startswith("login:identifier:")
    assert key == _storage_key("login:identifier", "person@example.com")  # normalised

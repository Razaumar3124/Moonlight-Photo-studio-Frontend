from datetime import UTC, datetime, timedelta

import pytest
from bson import ObjectId
from httpx import AsyncClient

from app.core.security import hash_password
from app.models.user import UserInDB
from app.services.email_service import email_service
from app.services.rate_limiter import rate_limiter
from tests.fakes import FakeSessionRepository, FakeUserRepository


@pytest.fixture(autouse=True)
async def setup_reset_user(fake_user_repo: FakeUserRepository):
    """Seed an active user for password recovery tests and reset limits."""
    rate_limiter.clear_all()
    email_service.mock_sent_emails.clear()

    now = datetime.now(UTC)
    user = UserInDB(
        _id=str(ObjectId()),
        email="customer.reset@safstudio.com",
        phone="+919876543210",
        password_hash=hash_password("OriginalPassword123!"),
        full_name="Aarav Sharma",
        role="customer",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    await fake_user_repo.create(user)


@pytest.mark.asyncio
async def test_forgot_password_registered_email(
    client: AsyncClient, fake_session_repo: FakeSessionRepository
):
    """EP-AUTH-06: Registered email receives 200 OK, OTP record in DB, and email dispatched."""
    payload = {"email": "customer.reset@safstudio.com"}
    response = await client.post("/api/v1/auth/forgot-password", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert "If an account is associated with this email" in data["message"]
    assert data["cooldown_seconds"] == 60

    # Verify email was dispatched via EmailService mock
    assert len(email_service.mock_sent_emails) == 1
    sent_mail = email_service.mock_sent_emails[0]
    assert sent_mail["to"] == "customer.reset@safstudio.com"
    otp_code = sent_mail["otp_code"]
    assert len(otp_code) == 6
    assert otp_code.isdigit()

    # Verify OTP challenge was recorded in DB
    active_otp = await fake_session_repo.get_active_otp("customer.reset@safstudio.com")
    assert active_otp is not None
    assert active_otp.purpose == "email_otp"
    assert active_otp.used is False
    assert active_otp.attempts == 0


@pytest.mark.asyncio
async def test_forgot_password_unregistered_email_non_enumerating(
    client: AsyncClient, fake_session_repo: FakeSessionRepository
):
    """EP-AUTH-06: Unknown email returns identical 200 without creating OTP or sending email."""
    payload = {"email": "nonexistent.user@safstudio.com"}
    response = await client.post("/api/v1/auth/forgot-password", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert "If an account is associated with this email" in data["message"]
    assert data["cooldown_seconds"] == 60

    assert len(email_service.mock_sent_emails) == 0
    assert len(fake_session_repo.password_resets) == 0


@pytest.mark.asyncio
async def test_forgot_password_invalid_email_format(client: AsyncClient):
    """EP-AUTH-06: Invalid email syntax returns 422 unprocessable entity."""
    payload = {"email": "not-a-valid-email"}
    response = await client.post("/api/v1/auth/forgot-password", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_forgot_password_cooldown_enforcement(client: AsyncClient):
    """EP-AUTH-06: Requesting OTP before 60s cooldown expires returns 429 Too Many Requests."""
    payload = {"email": "customer.reset@safstudio.com"}

    first_resp = await client.post("/api/v1/auth/forgot-password", json=payload)
    assert first_resp.status_code == 200

    # Immediate second request should be rejected by 60s cooldown
    second_resp = await client.post("/api/v1/auth/forgot-password", json=payload)
    assert second_resp.status_code == 429
    err = second_resp.json().get("error") or second_resp.json().get("detail")
    assert "Please wait" in err["message"]


@pytest.mark.asyncio
async def test_verify_otp_success(client: AsyncClient, fake_session_repo: FakeSessionRepository):
    """EP-AUTH-07: Submitting valid OTP consumes challenge and returns single-use reset token."""
    # 1. Request OTP
    req_resp = await client.post(
        "/api/v1/auth/forgot-password", json={"email": "customer.reset@safstudio.com"}
    )
    assert req_resp.status_code == 200
    otp_code = email_service.mock_sent_emails[0]["otp_code"]

    # 2. Verify OTP
    verify_resp = await client.post(
        "/api/v1/auth/forgot-password/verify",
        json={"email": "customer.reset@safstudio.com", "otp": otp_code},
    )
    assert verify_resp.status_code == 200
    data = verify_resp.json()
    assert "reset_token" in data
    assert data["reset_token"].startswith("rst_")
    assert data["expires_in_seconds"] == 600

    # 3. Verify OTP in DB is marked used
    active_otp = await fake_session_repo.get_active_otp("customer.reset@safstudio.com")
    assert active_otp is None


@pytest.mark.asyncio
async def test_verify_otp_invalid_code_decrements_attempts(client: AsyncClient):
    """EP-AUTH-07: Submitting wrong OTP returns 400/422 with remaining attempts."""
    await client.post(
        "/api/v1/auth/forgot-password", json={"email": "customer.reset@safstudio.com"}
    )

    verify_resp = await client.post(
        "/api/v1/auth/forgot-password/verify",
        json={"email": "customer.reset@safstudio.com", "otp": "000000"},
    )
    assert verify_resp.status_code in (400, 422)
    err = verify_resp.json().get("error") or verify_resp.json().get("detail")
    assert "2 attempt(s) remaining" in err["message"]


@pytest.mark.asyncio
async def test_verify_otp_max_attempts_lockout(client: AsyncClient):
    """EP-AUTH-07: 3 incorrect attempts permanently locks the OTP challenge."""
    await client.post(
        "/api/v1/auth/forgot-password", json={"email": "customer.reset@safstudio.com"}
    )

    # 3 attempts with incorrect code: 3rd attempt locks with max attempts exceeded
    last_resp = None
    for _ in range(3):
        last_resp = await client.post(
            "/api/v1/auth/forgot-password/verify",
            json={"email": "customer.reset@safstudio.com", "otp": "111111"},
        )
        assert last_resp.status_code in (400, 422)

    err = last_resp.json().get("error") or last_resp.json().get("detail")
    assert "Maximum verification attempts exceeded" in err["message"]


@pytest.mark.asyncio
async def test_verify_otp_expired(client: AsyncClient, fake_session_repo: FakeSessionRepository):
    """EP-AUTH-07: Verifying an expired OTP returns 400/422 Bad Request."""
    await client.post(
        "/api/v1/auth/forgot-password", json={"email": "customer.reset@safstudio.com"}
    )
    otp_code = email_service.mock_sent_emails[0]["otp_code"]

    # Artificially expire the OTP
    for doc in fake_session_repo.password_resets.values():
        if doc.get("purpose") == "email_otp":
            doc["expires_at"] = datetime.now(UTC) - timedelta(minutes=1)

    verify_resp = await client.post(
        "/api/v1/auth/forgot-password/verify",
        json={"email": "customer.reset@safstudio.com", "otp": otp_code},
    )
    assert verify_resp.status_code in (400, 422)
    err = verify_resp.json().get("error") or verify_resp.json().get("detail")
    assert "expired" in err["message"].lower()


@pytest.mark.asyncio
async def test_verify_otp_cannot_reuse(client: AsyncClient):
    """EP-AUTH-07: An already consumed OTP cannot be redeemed a second time."""
    await client.post(
        "/api/v1/auth/forgot-password", json={"email": "customer.reset@safstudio.com"}
    )
    otp_code = email_service.mock_sent_emails[0]["otp_code"]

    # First verify: 200 OK
    first = await client.post(
        "/api/v1/auth/forgot-password/verify",
        json={"email": "customer.reset@safstudio.com", "otp": otp_code},
    )
    assert first.status_code == 200

    # Second verify: 400/422
    second = await client.post(
        "/api/v1/auth/forgot-password/verify",
        json={"email": "customer.reset@safstudio.com", "otp": otp_code},
    )
    assert second.status_code in (400, 422)


@pytest.mark.asyncio
async def test_complete_recovery_flow_and_login_with_new_password(client: AsyncClient):
    """EP-AUTH-06, EP-AUTH-07, EP-AUTH-08: Full end-to-end recovery updates password."""
    # 1. Request OTP
    await client.post(
        "/api/v1/auth/forgot-password", json={"email": "customer.reset@safstudio.com"}
    )
    otp_code = email_service.mock_sent_emails[0]["otp_code"]

    # 2. Verify OTP
    verify_resp = await client.post(
        "/api/v1/auth/forgot-password/verify",
        json={"email": "customer.reset@safstudio.com", "otp": otp_code},
    )
    assert verify_resp.status_code == 200
    reset_token = verify_resp.json()["reset_token"]

    # 3. Reset Password
    new_password = "BrandNewPassword2026!"
    reset_resp = await client.post(
        "/api/v1/auth/forgot-password/reset",
        json={"reset_token": reset_token, "new_password": new_password},
    )
    assert reset_resp.status_code == 200
    assert "successfully reset" in reset_resp.json()["message"].lower()

    # 4. Old password should now fail login
    old_login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "customer.reset@safstudio.com", "password": "OriginalPassword123!"},
    )
    assert old_login.status_code == 401

    # 5. New password should successfully login
    new_login = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "customer.reset@safstudio.com", "password": new_password},
    )
    assert new_login.status_code == 200
    assert "tokens" in new_login.json()


@pytest.mark.asyncio
async def test_reset_password_rejects_reused_password(client: AsyncClient):
    """EP-AUTH-08: Submitting the current password is rejected with 400 Bad Request."""
    await client.post(
        "/api/v1/auth/forgot-password", json={"email": "customer.reset@safstudio.com"}
    )
    otp_code = email_service.mock_sent_emails[0]["otp_code"]

    verify_resp = await client.post(
        "/api/v1/auth/forgot-password/verify",
        json={"email": "customer.reset@safstudio.com", "otp": otp_code},
    )
    reset_token = verify_resp.json()["reset_token"]

    # Attempting to reuse original password
    reset_resp = await client.post(
        "/api/v1/auth/forgot-password/reset",
        json={"reset_token": reset_token, "new_password": "OriginalPassword123!"},
    )
    assert reset_resp.status_code in (400, 422)
    err = reset_resp.json().get("error") or reset_resp.json().get("detail")
    assert "cannot be the same" in err["message"].lower()


@pytest.mark.asyncio
async def test_reset_password_token_single_use(client: AsyncClient):
    """EP-AUTH-08: Reset token is consumed atomically and cannot be reused."""
    await client.post(
        "/api/v1/auth/forgot-password", json={"email": "customer.reset@safstudio.com"}
    )
    otp_code = email_service.mock_sent_emails[0]["otp_code"]

    verify_resp = await client.post(
        "/api/v1/auth/forgot-password/verify",
        json={"email": "customer.reset@safstudio.com", "otp": otp_code},
    )
    reset_token = verify_resp.json()["reset_token"]

    # First reset: 200 OK
    first = await client.post(
        "/api/v1/auth/forgot-password/reset",
        json={"reset_token": reset_token, "new_password": "NewPassword123!"},
    )
    assert first.status_code == 200

    # Second reset with same token: 401 Unauthorized
    second = await client.post(
        "/api/v1/auth/forgot-password/reset",
        json={"reset_token": reset_token, "new_password": "AnotherPassword456!"},
    )
    assert second.status_code == 401


@pytest.mark.asyncio
async def test_password_reset_revokes_previous_access_tokens(client: AsyncClient):
    """EP-AUTH-08: Resetting password invalidates all previously issued Bearer access tokens."""
    # 1. Login with original password and get access token
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"identifier": "customer.reset@safstudio.com", "password": "OriginalPassword123!"},
    )
    assert login_resp.status_code == 200
    old_access_token = login_resp.json()["tokens"]["access_token"]

    # 2. Access token works before reset
    me_before = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {old_access_token}"}
    )
    assert me_before.status_code == 200

    # 3. Execute password reset
    rate_limiter.clear_all()
    await client.post(
        "/api/v1/auth/forgot-password", json={"email": "customer.reset@safstudio.com"}
    )
    otp_code = email_service.mock_sent_emails[-1]["otp_code"]

    verify_resp = await client.post(
        "/api/v1/auth/forgot-password/verify",
        json={"email": "customer.reset@safstudio.com", "otp": otp_code},
    )
    reset_token = verify_resp.json()["reset_token"]

    reset_resp = await client.post(
        "/api/v1/auth/forgot-password/reset",
        json={"reset_token": reset_token, "new_password": "BrandNewPassword123!"},
    )
    assert reset_resp.status_code == 200

    # 4. Old access token MUST now be revoked and rejected on /auth/me
    me_after = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {old_access_token}"}
    )
    assert me_after.status_code == 401
    err = me_after.json().get("error") or me_after.json().get("detail")
    assert "token" in err["code"].lower()

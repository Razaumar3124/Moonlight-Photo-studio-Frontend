"""Tests for Resend Testing Mode integration in SAF email verification flow.

Verifies:
1. Recipient restriction to abdurrazzakshaikh31@gmail.com during development.
2. Graceful error handling for Resend API failures without leaking sensitive credentials.
3. Configurable test mode flag enabling transition to custom domains.
4. Complete OTP verification lifecycle.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core.config import Settings
from app.core.security import generate_otp, hash_otp, verify_otp_hash
from app.services.email_service import EmailDeliveryException, EmailService


@pytest.fixture
def test_mode_settings() -> Settings:
    """Settings with Resend testing mode enabled."""
    return Settings(
        ENVIRONMENT="development",
        SECRET_KEY="test-secret-key-min-32-chars-resend-testing-saf",
        EMAIL_PROVIDER="resend",
        RESEND_API_KEY="re_test_dummy_key_not_real",
        RESEND_FROM_EMAIL="SAF Studio <onboarding@resend.dev>",
        RESEND_TEST_MODE=True,
        RESEND_TEST_RECIPIENT="abdurrazzakshaikh31@gmail.com",
    )


@pytest.mark.asyncio
async def test_resend_testing_mode_permits_allowed_recipient(test_mode_settings: Settings):
    """Resend testing mode allows delivery to abdurrazzakshaikh31@gmail.com."""
    service = EmailService()

    with patch("app.services.email_service.get_settings", return_value=test_mode_settings):
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_resp = httpx.Response(
                status_code=200,
                json={"id": "email_123"},
                request=httpx.Request("POST", "https://api.resend.com/emails"),
            )
            mock_post.return_value = mock_resp

            result = await service.send_otp_email(
                to_email="abdurrazzakshaikh31@gmail.com",
                otp_code="123456",
            )
            assert result is True
            assert mock_post.called

            # Verify payload used onboarding@resend.dev and allowed recipient
            sent_payload = mock_post.call_args[1]["json"]
            assert sent_payload["from"] == "SAF Studio <onboarding@resend.dev>"
            assert sent_payload["to"] == ["abdurrazzakshaikh31@gmail.com"]
            assert "123456" in sent_payload["subject"]


@pytest.mark.asyncio
async def test_resend_testing_mode_case_insensitive_matching(test_mode_settings: Settings):
    """Recipient matching is case-insensitive (e.g. AbdurrazzakShaikh31@gmail.com)."""
    service = EmailService()

    with patch("app.services.email_service.get_settings", return_value=test_mode_settings):
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_resp = httpx.Response(
                status_code=200,
                json={"id": "email_456"},
                request=httpx.Request("POST", "https://api.resend.com/emails"),
            )
            mock_post.return_value = mock_resp

            result = await service.send_otp_email(
                to_email="AbdurrazzakShaikh31@GMAIL.COM",
                otp_code="654321",
            )
            assert result is True


@pytest.mark.asyncio
async def test_resend_testing_mode_blocks_unauthorized_recipient(test_mode_settings: Settings):
    """Resend testing mode blocks non-allowed recipient before calling external API."""
    service = EmailService()

    with patch("app.services.email_service.get_settings", return_value=test_mode_settings):
        with patch("httpx.AsyncClient.post") as mock_post:
            with pytest.raises(EmailDeliveryException) as exc_info:
                await service.send_otp_email(
                    to_email="random.customer@example.com",
                    otp_code="112233",
                )

            # External API must NOT be called
            assert not mock_post.called

            # Error message must give clean, helpful guidance
            err_msg = str(exc_info.value.message)
            assert "abdurrazzakshaikh31@gmail.com" in err_msg
            assert "resend.com/domains" in err_msg
            assert exc_info.value.code == "EMAIL_DELIVERY_FAILED"


@pytest.mark.asyncio
async def test_resend_testing_mode_configurable_toggle():
    """Setting RESEND_TEST_MODE=False allows sending to any recipient."""
    prod_settings = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="test-secret-key-min-32-chars-resend-testing-saf",
        EMAIL_PROVIDER="resend",
        RESEND_API_KEY="re_test_dummy_key_not_real",
        RESEND_FROM_EMAIL="SAF Studio <security@safstudio.com>",
        RESEND_TEST_MODE=False,
        CORS_ORIGINS=["https://safstudio.com"],
    )
    service = EmailService()

    with patch("app.services.email_service.get_settings", return_value=prod_settings):
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_resp = httpx.Response(
                status_code=200,
                json={"id": "email_prod_789"},
                request=httpx.Request("POST", "https://api.resend.com/emails"),
            )
            mock_post.return_value = mock_resp

            # Any recipient should now be allowed
            result = await service.send_otp_email(
                to_email="customer@anydomain.com",
                otp_code="998877",
            )
            assert result is True
            assert mock_post.called


@pytest.mark.asyncio
async def test_resend_api_403_testing_error_handled_gracefully(test_mode_settings: Settings):
    """Resend 403 testing rejection is translated to a clean user-safe message."""
    service = EmailService()

    resend_403_body = {
        "statusCode": 403,
        "name": "validation_error",
        "message": (
            "You can only send testing emails to your own email address (abdurrazzakshaikh31@gmail.com). "
            "To send emails to other recipients, please verify a domain at resend.com/domains, "
            "and change the `from` address to an email using this domain."
        ),
    }

    with patch("app.services.email_service.get_settings", return_value=test_mode_settings):
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_resp = httpx.Response(
                status_code=403,
                json=resend_403_body,
                request=httpx.Request("POST", "https://api.resend.com/emails"),
            )
            mock_post.return_value = mock_resp

            with pytest.raises(EmailDeliveryException) as exc_info:
                await service.send_otp_email(
                    to_email="abdurrazzakshaikh31@gmail.com",
                    otp_code="123456",
                )

            assert "testing mode" in exc_info.value.message.lower()
            assert "resend.com/domains" in exc_info.value.message.lower()
            # Must not expose raw API key or internal structures
            assert "re_" not in exc_info.value.message


@pytest.mark.asyncio
async def test_resend_api_timeout_handled_gracefully(test_mode_settings: Settings):
    """HTTP timeout raises EmailDeliveryException with user-safe message."""
    service = EmailService()

    with patch("app.services.email_service.get_settings", return_value=test_mode_settings):
        with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Timeout")):
            with pytest.raises(EmailDeliveryException) as exc_info:
                await service.send_otp_email(
                    to_email="abdurrazzakshaikh31@gmail.com",
                    otp_code="123456",
                )

            assert "timed out" in exc_info.value.message.lower()


@pytest.mark.asyncio
async def test_otp_lifecycle_generation_hash_and_verification():
    """Verify OTP generation, HMAC-SHA256 hashing, and verification."""
    email = "abdurrazzakshaikh31@gmail.com"

    # 1. Generation
    otp = generate_otp()
    assert len(otp) == 6
    assert otp.isdigit()

    # 2. Hashing
    otp_hash = hash_otp(email, otp)
    assert len(otp_hash) == 64  # SHA-256 hex string

    # 3. Valid verification
    assert verify_otp_hash(email, otp, otp_hash) is True

    # 4. Invalid OTP rejected
    assert verify_otp_hash(email, "000000", otp_hash) is False

    # 5. Wrong email rejected (email-bound)
    assert verify_otp_hash("other@gmail.com", otp, otp_hash) is False


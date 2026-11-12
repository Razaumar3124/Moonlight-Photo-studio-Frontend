import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.exceptions import AppException

logger = logging.getLogger("moonlight_studio.email")


class EmailDeliveryException(AppException):
    """Raised when transactional email dispatch fails."""

    def __init__(
        self,
        message: str = "Unable to deliver verification code. Please try again later.",
        issue: str = "Email provider delivery failure",
    ):
        super().__init__(
            message=message,
            code="EMAIL_DELIVERY_FAILED",
            status_code=503,
            details=[{"field": "email", "issue": issue}],
        )


def render_otp_email_html(otp_code: str, expiry_minutes: int = 10) -> str:
    """Render the branded HTML email for Moonlight Photo Studio password recovery.

    Moonlight palette (docs/DESIGN_SYSTEM.md): cream paper, crimson, fine gold rules, serif
    heading. Table layout with inline styles and system fonts, so it renders the same in
    mail clients that strip <style> blocks or block remote content.
    """
    serif = "Georgia, 'Times New Roman', serif"
    sans = "-apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
    year = datetime.now(UTC).year
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="color-scheme" content="light">
  <title>Your Moonlight Photo Studio verification code</title>
</head>
<body style="margin:0;padding:0;background-color:#FDF6EC;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background-color:#FDF6EC;padding:32px 12px;">
    <tr><td align="center">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
             style="max-width:560px;background-color:#FFFCF7;border:1px solid #EFDFC9;
                    border-top:3px solid #9B1118;border-radius:16px;">
        <tr><td align="center" style="padding:32px 40px 8px;font-family:{sans};">
          <div style="font-size:11px;letter-spacing:4px;text-transform:uppercase;
                      color:#8C6A2F;font-weight:600;">Est. 1985</div>
          <div style="font-family:{serif};font-size:26px;color:#9B1118;margin-top:6px;">
            Moonlight Photo Studio</div>
          <div style="width:56px;height:1px;background-color:#C9A25A;margin:16px auto 0;
                      line-height:1px;font-size:1px;">&nbsp;</div>
        </td></tr>
        <tr><td align="center" style="padding:24px 40px 8px;font-family:{sans};color:#4A3329;">
          <h1 style="font-family:{serif};font-size:22px;font-weight:600;color:#2A1712;
                     margin:0 0 12px;">Reset your password</h1>
          <p style="font-size:15px;line-height:24px;margin:0 0 28px;">
            We received a request to reset the password for your Moonlight Photo Studio
            account. Enter this 6-digit code to continue:</p>
          <div style="display:inline-block;background-color:#F8ECDC;border:1px solid #EFDFC9;
                      border-radius:10px;padding:14px 32px;margin-bottom:24px;">
            <span style="font-family:Consolas,'SF Mono',Menlo,monospace;font-size:34px;
                         font-weight:700;letter-spacing:8px;color:#2A1712;">{otp_code}</span>
          </div>
          <p style="font-size:14px;line-height:22px;color:#7A6356;margin:0 0 24px;">
            This code expires in <strong style="color:#4A3329;">{expiry_minutes} minutes</strong>.
            Never share it with anyone, including our team.</p>
        </td></tr>
        <tr><td style="padding:0 40px 32px;font-family:{sans};">
          <div style="border-left:3px solid #C9A25A;background-color:#FDF6EC;padding:14px 18px;
                      font-size:13px;line-height:20px;color:#4A3329;">
            <strong>Didn’t ask for this?</strong> You can ignore this email. Your current
            password stays active.</div>
        </td></tr>
        <tr><td align="center" style="padding:20px 40px;border-top:1px solid #EFDFC9;
                                       font-family:{sans};font-size:12px;color:#7A6356;">
          &copy; {year} Moonlight Photo Studio · This is an automated message; replies
          aren’t monitored.
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def render_otp_email_text(otp_code: str, expiry_minutes: int = 10) -> str:
    """Render plain-text fallback email for clients with HTML disabled."""
    return f"""MOONLIGHT PHOTO STUDIO — PASSWORD RESET CODE
------------------------------------------------------
Your 6-digit verification code is: {otp_code}

This code expires in {expiry_minutes} minutes.

If you did not request a password reset, please ignore this email.
Your account remains secure.

— Moonlight Photo Studio
"""


class EmailService:
    """Asynchronous transactional email service supporting Resend and Mock providers."""

    def __init__(self) -> None:
        self.mock_sent_emails: list[dict[str, Any]] = []

    async def send_otp_email(
        self,
        to_email: str,
        otp_code: str,
        expiry_minutes: int | None = None,
    ) -> bool:
        """Dispatch branded 6-digit OTP email via Resend or recording mock."""
        settings = get_settings()
        expire_mins = expiry_minutes or settings.EMAIL_OTP_EXPIRE_MINUTES

        subject = f"{otp_code} is your Moonlight Photo Studio verification code"
        html_body = render_otp_email_html(otp_code, expire_mins)
        text_body = render_otp_email_text(otp_code, expire_mins)

        # 1. Mock provider (used for testing and explicit offline dev)
        if settings.EMAIL_PROVIDER == "mock":
            record = {
                "to": to_email,
                "subject": subject,
                "otp_code": otp_code,
                "expiry_minutes": expire_mins,
            }
            self.mock_sent_emails.append(record)
            if settings.is_development:
                logger.debug(
                    "[DEV ONLY MOCK] OTP for %s: %s (expires in %d min)",
                    to_email,
                    otp_code,
                    expire_mins,
                )
            else:
                logger.info("Mock email recorded for recipient %s", to_email)
            return True

        # 2. Resend production/live provider
        if settings.EMAIL_PROVIDER == "resend":
            if not settings.RESEND_API_KEY.strip():
                logger.error("EMAIL_PROVIDER is 'resend' but RESEND_API_KEY is missing or empty")
                raise EmailDeliveryException(
                    message="Email delivery service is misconfigured.",
                    issue="Missing RESEND_API_KEY",
                )

            # Enforce Resend Testing Mode recipient restriction
            if settings.RESEND_TEST_MODE:
                allowed_recipient = (settings.RESEND_TEST_RECIPIENT or "").strip().lower()
                norm_to_email = to_email.strip().lower()
                if allowed_recipient and norm_to_email != allowed_recipient:
                    # The allowed address is a developer's inbox: log it, never return it.
                    logger.warning(
                        "Resend testing mode blocked dispatch to '%s'; only '%s' is permitted.",
                        to_email,
                        allowed_recipient,
                    )
                    raise EmailDeliveryException(
                        message=(
                            "Email delivery is in testing mode and can only reach the configured "
                            "test recipient. Verify a sending domain at resend.com/domains to "
                            "email other recipients."
                        ),
                        issue="Recipient not allowed in Resend test mode",
                    )

            payload = {
                "from": settings.RESEND_FROM_EMAIL,
                "to": [to_email],
                "subject": subject,
                "html": html_body,
                "text": text_body,
            }

            headers = {
                "Authorization": f"Bearer {settings.RESEND_API_KEY.strip()}",
                "Content-Type": "application/json",
            }

            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(
                        "https://api.resend.com/emails",
                        json=payload,
                        headers=headers,
                    )

                if resp.status_code in (200, 201):
                    logger.info("Verification OTP email dispatched via Resend to %s", to_email)
                    return True

                # Parse Resend response safely without leaking credentials or raw payloads
                error_message = "Failed to deliver verification code via email."
                issue_summary = f"Resend HTTP {resp.status_code}"
                try:
                    resend_json = resp.json()
                    resend_msg = resend_json.get("message", "")
                    if resp.status_code == 403 and "testing emails" in resend_msg.lower():
                        error_message = (
                            "Resend is in testing mode and can only deliver to the verified "
                            "account owner. Verify a sending domain at resend.com/domains to "
                            "email other recipients."
                        )
                        issue_summary = "Resend 403 testing recipient restriction"
                    elif resp.status_code == 422:
                        error_message = "Email delivery service rejected recipient address format."
                        issue_summary = "Resend 422 validation error"
                    elif resp.status_code == 429:
                        error_message = (
                            "Email delivery rate limit reached. Please wait a moment and try again."
                        )
                        issue_summary = "Resend 429 rate limit exceeded"
                    elif resp.status_code == 401:
                        error_message = "Email delivery service authentication error."
                        issue_summary = "Resend 401 unauthorized"
                except Exception:
                    pass

                logger.error(
                    "Resend API delivery rejected: status=%d issue=%s",
                    resp.status_code,
                    issue_summary,
                )
                raise EmailDeliveryException(
                    message=error_message,
                    issue=issue_summary,
                )

            except httpx.TimeoutException as exc:
                logger.error("Resend API timed out after 5.0 seconds")
                raise EmailDeliveryException(
                    message="Email delivery service timed out. Please try again.",
                    issue="Resend timeout",
                ) from exc
            except httpx.RequestError as exc:
                logger.error("Resend connection error: %s", exc)
                raise EmailDeliveryException(
                    message="Network error communicating with email provider.",
                    issue="Connection error communicating with email provider",
                ) from exc

        logger.error("Unknown EMAIL_PROVIDER: %s", settings.EMAIL_PROVIDER)
        raise EmailDeliveryException(
            message="Unsupported email provider configuration.",
            issue=f"Unknown provider '{settings.EMAIL_PROVIDER}'",
        )

    async def check_health(self) -> dict[str, Any]:
        """Verify transactional email provider status."""
        import time

        settings = get_settings()
        if settings.EMAIL_PROVIDER == "mock":
            return {
                "status": "ready",
                "provider": "mock",
                "from_email": settings.RESEND_FROM_EMAIL,
                "mock_emails_queued": len(self.mock_sent_emails),
            }

        if settings.EMAIL_PROVIDER == "resend":
            api_key = settings.RESEND_API_KEY.strip()
            if not api_key:
                return {
                    "status": "misconfigured",
                    "provider": "resend",
                    "from_email": settings.RESEND_FROM_EMAIL,
                    "issue": "RESEND_API_KEY is not set",
                }

            start = time.perf_counter()
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    resp = await client.get(
                        "https://api.resend.com/api-keys",
                        headers={"Authorization": f"Bearer {api_key}"},
                    )
                latency = round((time.perf_counter() - start) * 1000, 2)
                if resp.status_code == 200:
                    health_info: dict[str, Any] = {
                        "status": "ready",
                        "provider": "resend",
                        "from_email": settings.RESEND_FROM_EMAIL,
                        "latency_ms": latency,
                        "test_mode": settings.RESEND_TEST_MODE,
                    }
                    if settings.RESEND_TEST_MODE:
                        health_info["test_recipient"] = settings.RESEND_TEST_RECIPIENT
                    return health_info
                return {
                    "status": "degraded",
                    "provider": "resend",
                    "from_email": settings.RESEND_FROM_EMAIL,
                    "issue": f"Resend API returned HTTP {resp.status_code}",
                    "latency_ms": latency,
                }
            except Exception as exc:
                return {
                    "status": "unreachable",
                    "provider": "resend",
                    "from_email": settings.RESEND_FROM_EMAIL,
                    "issue": str(exc),
                }

        return {
            "status": "unknown_provider",
            "provider": settings.EMAIL_PROVIDER,
            "issue": f"Unsupported provider: {settings.EMAIL_PROVIDER}",
        }


# Global singleton instance for injection and test inspection
email_service = EmailService()

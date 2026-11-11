"""WhatsApp Click-to-Chat integration and formatted message composer.

Constructs official WhatsApp Click-to-Chat URLs (wa.me) with prefilled,
structured message summaries for SAF Studio Memory Wall quote requests.
"""

import urllib.parse
from typing import Any

from app.core.config import get_settings


class WhatsAppService:
    """Service for building clean, user-friendly WhatsApp Click-to-Chat URLs."""

    STYLE_LABELS: dict[str, str] = {
        "grid": "Gallery Grid",
        "salon": "Salon Arrangement",
        "centre": "Centre Anchor",
        "row": "Linear Row",
        "linear": "Linear Row",
        "custom": "Custom Arrangement",
    }

    FINISH_LABELS: dict[str, str] = {
        "natural-oak": "Natural Oak",
        "dark-walnut": "Dark Walnut",
        "matte-black": "Matte Black",
        "warm-metallic": "Warm Metallic",
        "white-ash": "White Ash",
        "raw-pine": "Raw Pine",
    }

    def __init__(self, business_number: str | None = None) -> None:
        settings = get_settings()
        self.business_number = (
            (business_number or settings.BUSINESS_WHATSAPP_NUMBER)
            .strip()
            .lstrip("+")
            .replace(" ", "")
            .replace("-", "")
        )

    def format_style_label(self, raw_style: str) -> str:
        """Format layout style identifier to customer-facing display name."""
        norm = raw_style.strip().lower()
        return self.STYLE_LABELS.get(norm, norm.replace("-", " ").title())

    def format_finish_summary(self, finish_ids: list[str]) -> str:
        """Format single or mixed frame finishes into a human-readable summary."""
        if not finish_ids:
            return "Standard Finish"

        unique_labels = []
        for fid in finish_ids:
            label = self.FINISH_LABELS.get(fid, fid.replace("-", " ").title())
            if label not in unique_labels:
                unique_labels.append(label)

        if len(unique_labels) == 1:
            return unique_labels[0]
        elif len(unique_labels) <= 3:
            return f"Mixed ({', '.join(unique_labels)})"
        return f"Mixed Finishes ({len(unique_labels)} styles)"

    def build_quote_message(
        self,
        quote_reference: str,
        wall_width: float,
        wall_height: float,
        display_unit: str,
        arrangement_style: str,
        frame_count: int,
        finish_summary: str,
        report_url: str,
        customer_name: str,
        customer_mobile: str | None = None,
        customer_email: str | None = None,
    ) -> str:
        """Compose clean, professional WhatsApp quote request message matching SAF branding."""
        unit_label = "inches" if display_unit in ("in", "inch", "inches") else display_unit

        # Format dimensions cleanly (avoid 120.0 if integer)
        w_str = f"{wall_width:g}"
        h_str = f"{wall_height:g}"
        style_display = self.format_style_label(arrangement_style)

        # Format customer contact lines
        contact_lines = [f"Name: {customer_name.strip()}"]
        if customer_mobile and customer_mobile.strip():
            phone_clean = customer_mobile.strip()
            if not phone_clean.startswith("+") and len(phone_clean) == 10:
                phone_clean = f"+91{phone_clean}"
            contact_lines.append(f"Mobile: {phone_clean}")
        elif customer_email and customer_email.strip():
            contact_lines.append(f"Email: {customer_email.strip()}")
        else:
            contact_lines.append("Mobile: Not provided")

        contact_text = "\n".join(contact_lines)

        message = (
            "Hello SAF Studio! 👋\n\n"
            "I'd like to request a quote for my Memory Wall design.\n\n"
            "*DESIGN DETAILS*\n"
            f"• Reference: {quote_reference}\n"
            f"• Wall Size: {w_str} × {h_str} {unit_label}\n"
            f"• Arrangement: {style_display}\n"
            f"• Frames: {frame_count}\n"
            f"• Finish: {finish_summary}\n\n"
            "*VIEW MY DESIGN*\n"
            f"{report_url}\n\n"
            "*CUSTOMER*\n"
            f"{contact_text}\n\n"
            "Please review my design and share the quotation.\n\n"
            "Thank you!"
        )
        return message

    def generate_whatsapp_url(self, message: str) -> str:
        """Encode message and construct official WhatsApp Click-to-Chat URL."""
        encoded_message = urllib.parse.quote(message, safe="")
        return f"https://wa.me/{self.business_number}?text={encoded_message}"

    def check_health(self) -> dict[str, Any]:
        """Verify WhatsApp configuration and Click-to-Chat readiness."""

        settings = get_settings()
        num = self.business_number
        is_placeholder = num in ("919876543210", "1234567890", "")
        is_valid_format = num.isdigit() and (10 <= len(num) <= 15)

        return {
            "status": "configured" if is_valid_format else "invalid_configuration",
            "business_number": num,
            "is_placeholder": is_placeholder,
            "is_valid_format": is_valid_format,
            "public_app_url": settings.PUBLIC_APP_URL,
        }

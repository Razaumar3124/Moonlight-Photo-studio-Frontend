"""Unit tests for WhatsApp Click-to-Chat URL and message generation."""

import urllib.parse

from app.services.whatsapp_service import WhatsAppService


def test_whatsapp_service_single_finish():
    service = WhatsAppService(business_number="919876543210")
    finish = service.format_finish_summary(["natural-oak", "natural-oak"])
    assert finish == "Natural Oak"

    msg = service.build_quote_message(
        quote_reference="SQ-2026-0012",
        wall_width=120,
        wall_height=96,
        display_unit="in",
        arrangement_style="grid",
        frame_count=9,
        finish_summary=finish,
        report_url="https://saf.studio/q/secure-token-123",
        customer_name="Priya Patel",
        customer_mobile="+919876543210",
    )

    assert "SQ-2026-0012" in msg
    assert "120 × 96 inches" in msg
    assert "Gallery Grid" in msg
    assert "Frames: 9" in msg
    assert "Finish: Natural Oak" in msg
    assert "https://saf.studio/q/secure-token-123" in msg
    assert "Name: Priya Patel" in msg
    assert "Mobile: +919876543210" in msg

    url = service.generate_whatsapp_url(msg)
    assert url.startswith("https://wa.me/919876543210?text=")
    # Unquote and verify
    unquoted = urllib.parse.unquote(url.split("?text=")[1])
    assert unquoted == msg


def test_whatsapp_service_mixed_finishes():
    service = WhatsAppService(business_number="919876543210")
    finish = service.format_finish_summary(["natural-oak", "matte-black"])
    assert "Mixed (Natural Oak, Matte Black)" in finish

    msg = service.build_quote_message(
        quote_reference="SQ-2026-0099",
        wall_width=144,
        wall_height=108,
        display_unit="ft",
        arrangement_style="salon",
        frame_count=7,
        finish_summary=finish,
        report_url="https://saf.studio/q/token-xyz",
        customer_name="Rahul Verma",
        customer_mobile="9876543210",
    )

    assert "Salon Arrangement" in msg
    assert "144 × 108 ft" in msg
    assert "Mixed (Natural Oak, Matte Black)" in msg
    assert "Mobile: +919876543210" in msg


def test_whatsapp_service_graceful_missing_mobile():
    service = WhatsAppService(business_number="919876543210")
    msg = service.build_quote_message(
        quote_reference="SQ-2026-0050",
        wall_width=100,
        wall_height=80,
        display_unit="cm",
        arrangement_style="centre",
        frame_count=4,
        finish_summary="Dark Walnut",
        report_url="https://saf.studio/q/token-abc",
        customer_name="Ananya Roy",
        customer_mobile=None,
        customer_email="ananya@example.com",
    )

    assert "Email: ananya@example.com" in msg
    assert "Mobile:" not in msg


def test_whatsapp_service_no_credential_leakage():
    service = WhatsAppService(business_number="+91 98765 43210")
    assert service.business_number == "919876543210"

    msg = service.build_quote_message(
        quote_reference="SQ-2026-0001",
        wall_width=120,
        wall_height=96,
        display_unit="in",
        arrangement_style="grid",
        frame_count=6,
        finish_summary="Natural Oak",
        report_url="https://saf.studio/q/clean-token",
        customer_name="Secret User",
    )

    # Ensure sensitive storage paths / tokens are not present
    assert "r2.cloudflarestorage.com" not in msg
    assert "AWS_SECRET" not in msg
    assert "ObjectId" not in msg
    assert "quotes/" not in msg

"""Digital Design Report rendering service for quotation requests."""

from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.models.quote import QuoteFrameSnapshot, QuoteInDB
from app.modules import catalog
from app.schemas.quote import QuoteFrameSummaryOut, QuoteShareResponse
from app.services.whatsapp_service import WhatsAppService


class QuoteReportService:
    """Service to render responsive, branded HTML reports and public share models."""

    def __init__(self, templates_dir: Path | str | None = None) -> None:
        if templates_dir is None:
            base_dir = Path(__file__).resolve().parent.parent
            templates_dir = base_dir / "templates"
        self.templates_dir = Path(templates_dir)
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )
        self.whatsapp_service = WhatsAppService()

    @staticmethod
    def mask_phone(phone: str | None) -> str:
        """Mask middle digits of phone number for sensitive sharing."""
        if not phone:
            return "Not provided"
        clean = phone.strip()
        if len(clean) >= 10:
            # Show first 3 and last 3 digits
            return f"{clean[:3]}••••{clean[-3:]}"
        return clean

    @staticmethod
    def mask_email(email: str) -> str:
        """Mask local part of email address."""
        if "@" not in email:
            return email
        local, domain = email.split("@", 1)
        if len(local) <= 2:
            return f"{local[0]}*@{domain}"
        return f"{local[0]}••••{local[-1]}@{domain}"

    @staticmethod
    def _opening(frame: QuoteFrameSnapshot) -> tuple[float, float] | None:
        """Photo opening as hung; derived from the size ID for quotes stored before Phase 3."""
        if frame.opening_width_inches and frame.opening_height_inches:
            return frame.opening_width_inches, frame.opening_height_inches
        size = catalog.get_frame_size(frame.size_id)
        if size:
            return size.oriented(frame.orientation)
        parts = frame.size_id.lower().replace("×", "x").replace(" ", "").split("x")
        try:
            w, h = (float(parts[0]), float(parts[1])) if len(parts) == 2 else (0.0, 0.0)
        except ValueError:
            return None
        if w <= 0 or h <= 0:
            return None
        return (max(w, h), min(w, h)) if frame.orientation == "landscape" else (w, h)

    def build_frame_spec_list(self, quote: QuoteInDB) -> list[QuoteFrameSummaryOut]:
        """Convert QuoteFrameSnapshot items into customer-facing specification summaries."""
        specs = []
        for f in quote.frames:
            opening = self._opening(f)
            size_str = (
                f"{opening[0]:g} × {opening[1]:g} in" if opening else catalog.humanize_id(f.size_id)
            )
            dim_str = f"{f.width_inches:g} × {f.height_inches:g} in"

            # Catalog label first; older quotes keep whatever label they stored.
            finish = catalog.get_finish(f.finish_id)
            finish_label = (
                finish.label if finish else f.finish_name or catalog.finish_label(f.finish_id)
            )

            if f.mount_enabled and f.mount_margin_inches > 0:
                colour = (
                    catalog.mount_colour_label(f.mount_color_id)
                    or catalog.mount_colour_label(f.mount_color_name)
                    or catalog.MOUNT_COLOURS[0].label
                )
                mount_str = f"{colour} ({f.mount_margin_inches:g} in border)"
            else:
                mount_str = "No mount"

            if f.photo_name:
                photo_str = f.photo_name
            elif f.photo_kind == "upload":
                photo_str = "Customer photograph"
            elif f.photo_kind == "sample":
                photo_str = f"Sample photograph ({f.sample_id or 'gallery'})"
            else:
                photo_str = "To be provided"

            specs.append(
                QuoteFrameSummaryOut(
                    number=f.frame_number,
                    size=size_str,
                    dimensions=dim_str,
                    orientation=f.orientation.title(),
                    finish=finish_label,
                    mount=mount_str,
                    photo=photo_str,
                )
            )
        return specs

    def render_report_html(self, quote: QuoteInDB, preview_url: str) -> str:
        """Render complete HTML design report with Jinja2 autoescaping."""
        template = self.env.get_template("quote_report.html")

        wall_dims = catalog.format_wall_size(
            quote.wall.width_inches, quote.wall.height_inches, quote.wall.display_unit
        )
        wall_inches_subtext = catalog.format_wall_size(
            quote.wall.width_inches, quote.wall.height_inches, "in"
        )

        # Arrangement style
        style_label = self.whatsapp_service.format_style_label(quote.layout_style)

        # Finish summary
        finish_ids = [f.finish_id for f in quote.frames]
        finish_summary = self.whatsapp_service.format_finish_summary(finish_ids)

        frame_specs = self.build_frame_spec_list(quote)

        formatted_date = quote.created_at.strftime("%B %d, %Y")
        formatted_expiry = quote.expires_at.strftime("%B %d, %Y")

        html = template.render(
            quote=quote,
            design_title=quote.design_title or "Memory Wall Design",
            wall_dimensions=wall_dims,
            wall_inches_subtext=wall_inches_subtext,
            arrangement_style=style_label,
            finish_summary=finish_summary,
            frame_specs=frame_specs,
            preview_url=preview_url,
            formatted_date=formatted_date,
            formatted_expiry=formatted_expiry,
            customer_phone_masked=self.mask_phone(quote.customer.phone),
            customer_email_masked=self.mask_email(quote.customer.email),
            current_year=datetime.now(UTC).year,
        )
        return html

    def build_share_response(self, quote: QuoteInDB, preview_url: str) -> QuoteShareResponse:
        """Construct read-only JSON model for API consumers of the shared report."""
        wall_dims = catalog.format_wall_size(
            quote.wall.width_inches, quote.wall.height_inches, quote.wall.display_unit
        )
        style_label = self.whatsapp_service.format_style_label(quote.layout_style)
        finish_ids = [f.finish_id for f in quote.frames]
        finish_summary = self.whatsapp_service.format_finish_summary(finish_ids)

        contact_masked = (
            self.mask_phone(quote.customer.phone)
            if quote.customer.phone
            else self.mask_email(quote.customer.email)
        )

        return QuoteShareResponse(
            quote_id=quote.quote_reference,
            created_at=quote.created_at.isoformat(),
            expires_at=quote.expires_at.isoformat(),
            customer_name=quote.customer.full_name,
            customer_contact_masked=contact_masked,
            design_title=quote.design_title or "Memory Wall Design",
            layout_style=style_label,
            wall_dimensions=wall_dims,
            frame_count=len(quote.frames),
            finish_summary=finish_summary,
            preview_image_url=preview_url,
            frames=self.build_frame_spec_list(quote),
        )

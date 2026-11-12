"""Moonlight planner catalog: the backend's source of truth for the Memory Wall options.

Every option the planner offers (frame sizes, wood finishes, mount colours, paint shades,
layout styles, measurement units) and every physical rule it applies (wall limits, margins,
sofa clearance, mat widths, frame counts) is defined here once, with a stable string ID.
Designs, quotes, layout generation and the share report all resolve IDs through this module,
and `GET /catalog` publishes it.

The frontend mirrors these values in `frontend/src/features/memory-wall/constants.ts` until
Phase 5 loads them from the API; `tests/test_catalog_contract.py` fails if the two drift.
IDs are permanent: add new ones, never rename or reuse old ones (stored designs and quotes
reference them).
"""

from dataclasses import dataclass
from typing import Annotated, Literal, get_args

from pydantic import AfterValidator

CATALOG_VERSION = "2026-11-12"

Orientation = Literal["portrait", "landscape"]
# Units the planner offers, plus "mm", which predates the planner and is still accepted from
# API clients and stored designs. Every API value is in inches regardless.
DisplayUnit = Literal["ft", "in", "cm", "m", "mm"]


@dataclass(frozen=True, slots=True)
class FrameSize:
    """Photo opening in inches, portrait orientation (short side first)."""

    id: str
    width_inches: float
    height_inches: float
    label: str
    recommended: bool = False

    def oriented(self, orientation: str) -> tuple[float, float]:
        """(width, height) of the opening as hung."""
        if orientation == "landscape":
            return self.height_inches, self.width_inches
        return self.width_inches, self.height_inches


@dataclass(frozen=True, slots=True)
class FrameFinish:
    """Wood moulding finish; `profile_inches` is the visible face width added on each side."""

    id: str
    label: str
    hex: str
    profile_inches: float


@dataclass(frozen=True, slots=True)
class Swatch:
    id: str
    label: str
    hex: str


FRAME_SIZES: tuple[FrameSize, ...] = (
    FrameSize("5x7", 5, 7, "5 x 7 inches"),
    FrameSize("8x10", 8, 10, "8 x 10 inches"),
    FrameSize("11x14", 11, 14, "11 x 14 inches"),
    FrameSize("12x16", 12, 16, "12 x 16 inches (Atelier Classic Recommended)", recommended=True),
    FrameSize("16x20", 16, 20, "16 x 20 inches"),
    FrameSize("18x24", 18, 24, "18 x 24 inches"),
    FrameSize("20x30", 20, 30, "20 x 30 inches"),
    FrameSize("24x36", 24, 36, "24 x 36 inches (Statement)"),
)

FRAME_FINISHES: tuple[FrameFinish, ...] = (
    FrameFinish("walnut", "Walnut", "#784E2D", 1.0),
    FrameFinish("natural-oak", "Natural Oak", "#916843", 1.0),
    FrameFinish("ivory", "Ivory", "#FAF3E8", 0.875),
    FrameFinish("whitewash", "Whitewash", "#EEE6DE", 0.875),
    FrameFinish("dark-teak", "Dark Teak", "#774B31", 1.0),
    FrameFinish("honey", "Honey", "#B1875F", 1.0),
    FrameFinish("golden-teak", "Golden Teak", "#B07840", 1.125),
    FrameFinish("mahogany", "Mahogany", "#7A432D", 1.125),
)

MOUNT_COLOURS: tuple[Swatch, ...] = (
    Swatch("museum-white", "Museum White", "#F4F3F3"),
    Swatch("antique-white", "Antique White", "#EDE8E3"),
    Swatch("black", "Black", "#1D191A"),
    Swatch("crimson", "Crimson", "#6B0A11"),
)

PAINT_SHADES: tuple[Swatch, ...] = (
    Swatch("ivory-mist", "Ivory Mist", "#F0EBE4"),
    Swatch("warm-cream", "Warm Cream", "#EFDECA"),
    Swatch("sand", "Sand", "#E4CFB4"),
    Swatch("peach-blush", "Peach Blush", "#ECCAAF"),
    Swatch("charcoal", "Charcoal", "#6F6A64"),
    Swatch("stone-grey", "Stone Grey", "#8D8785"),
    Swatch("cloud-grey", "Cloud Grey", "#C5C5C7"),
)

LAYOUT_STYLE_LABELS: dict[str, str] = {
    "grid": "Grid",
    "salon": "Salon",
    "centre": "Centre",
    "row": "Row",
}
LAYOUT_STYLE_IDS: tuple[str, ...] = tuple(LAYOUT_STYLE_LABELS)

# Template slugs the planner ships with (seeded by app/db/seed_catalog.py).
TEMPLATE_IDS: tuple[str, ...] = (
    "balanced-grid",
    "creative-salon",
    "centre-focus",
    "minimal-row",
    "classic-six",
    "triptych",
    "petite-salon",
    "statement-centre",
    "panorama-row",
    "grand-quad",
)

# Older names for the same layout (SAF contract and early template seeds). Accepted on input
# and normalised, so stored designs, quotes and templates keep working.
LEGACY_LAYOUT_ALIASES: dict[str, str] = {
    "focal_center": "centre",
    "center": "centre",
    "linear": "row",
    "triptych": "row",
}

WALL_UNITS: tuple[str, ...] = ("ft", "in", "cm", "m")
ACCEPTED_WALL_UNITS: tuple[str, ...] = get_args(DisplayUnit)
GAP_UNITS: tuple[str, ...] = ("in", "cm")

INCHES_PER_UNIT: dict[str, float] = {
    "in": 1.0,
    "ft": 12.0,
    "cm": 1 / 2.54,
    "m": 100 / 2.54,
    "mm": 1 / 25.4,
}
# Display precision per unit (matches frontend lib/units.ts formatLength).
UNIT_PRECISION: dict[str, int] = {"ft": 1, "in": 0, "cm": 0, "m": 2, "mm": 0}


@dataclass(frozen=True, slots=True)
class PlannerRules:
    """Physical rules of the planner, in inches (frontend PLANNER_RULES)."""

    eye_level_inches: float = 60.0
    wall_margin_inches: float = 6.0
    min_bottom_inches: float = 12.0
    sofa_clearance_inches: float = 8.0
    # Top of the reference sofa above the floor, measured on the planner's room photo:
    # (photo height 667 px - sofa top 492 px) at 1009 px per 84 in of sofa width.
    sofa_top_from_floor_inches: float = (667 - 492) * 84 / (1252 - 243)
    wall_width_min_inches: float = 36.0
    wall_width_max_inches: float = 480.0
    wall_height_min_inches: float = 48.0
    wall_height_max_inches: float = 240.0
    gap_min_inches: float = 0.0
    gap_max_inches: float = 12.0
    mat_min_inches: float = 0.0
    mat_max_inches: float = 6.0
    mat_step_inches: float = 0.5
    frame_count_min: int = 1
    frame_count_max: int = 16
    variant_count: int = 3
    default_profile_inches: float = 1.0

    def min_bottom(self, has_sofa: bool) -> float:
        """Lowest point the arrangement may reach, measured up from the floor."""
        if not has_sofa:
            return self.min_bottom_inches
        return max(
            self.min_bottom_inches,
            self.sofa_top_from_floor_inches + self.sofa_clearance_inches,
        )


RULES = PlannerRules()

_SIZES = {s.id: s for s in FRAME_SIZES}
_FINISHES = {f.id: f for f in FRAME_FINISHES}
_MOUNTS = {m.id: m for m in MOUNT_COLOURS}
_PAINTS = {p.id: p for p in PAINT_SHADES}


def get_frame_size(size_id: str | None) -> FrameSize | None:
    return _SIZES.get(size_id) if size_id else None


def get_finish(finish_id: str | None) -> FrameFinish | None:
    return _FINISHES.get(finish_id) if finish_id else None


def get_mount_colour(colour_id: str | None) -> Swatch | None:
    return _MOUNTS.get(colour_id) if colour_id else None


def get_paint_shade(paint_id: str | None) -> Swatch | None:
    return _PAINTS.get(paint_id) if paint_id else None


def size_for_dimensions(width: float, height: float) -> tuple[FrameSize, Orientation] | None:
    """Catalog size (and orientation) whose opening is `width` x `height`, if any."""
    for size in FRAME_SIZES:
        if _close(size.width_inches, width) and _close(size.height_inches, height):
            return size, "portrait"
        if _close(size.height_inches, width) and _close(size.width_inches, height):
            return size, "landscape"
    return None


def normalize_layout(value: str) -> str:
    """Lower-case a layout style / template category and map legacy names."""
    norm = value.strip().lower()
    return LEGACY_LAYOUT_ALIASES.get(norm, norm)


def layout_aliases(style: str) -> list[str]:
    """`style` plus every legacy name that normalises to it (for database queries)."""
    return [style, *sorted(k for k, v in LEGACY_LAYOUT_ALIASES.items() if v == style)]


def humanize_id(value: str) -> str:
    """Display text for an ID the catalog doesn't know (e.g. a legacy finish)."""
    return value.replace("-", " ").replace("_", " ").strip().title() or value


def finish_label(finish_id: str) -> str:
    finish = get_finish(finish_id)
    return finish.label if finish else humanize_id(finish_id)


def mount_colour_label(value: str | None) -> str | None:
    """Label for a mount colour given as a catalog ID or as an already-stored label."""
    if not value:
        return None
    colour = get_mount_colour(value)
    return colour.label if colour else value


def profile_inches(finish_id: str | None) -> float:
    finish = get_finish(finish_id)
    return finish.profile_inches if finish else RULES.default_profile_inches


def outer_size(
    opening_width: float,
    opening_height: float,
    profile: float,
    mat_left: float = 0.0,
    mat_right: float = 0.0,
    mat_top: float = 0.0,
    mat_bottom: float = 0.0,
) -> tuple[float, float]:
    """Outer frame size: opening + mats + the moulding face on both sides (frontend
    frameGeometry: `w + 2 * (mat + profile)`)."""
    return (
        round(opening_width + mat_left + mat_right + 2 * profile, 4),
        round(opening_height + mat_top + mat_bottom + 2 * profile, 4),
    )


# --------------------------------- Units ------------------------------------


def to_inches(value: float, unit: str) -> float:
    return value * INCHES_PER_UNIT[unit]


def from_inches(inches: float, unit: str) -> float:
    return inches / INCHES_PER_UNIT[unit]


def _plain_number(value: float, decimals: int) -> str:
    # Round half away from zero like the frontend's roundTo (Math.round(v + EPSILON)).
    factor = 10**decimals
    rounded = int(abs(value) * factor + 0.5 + 1e-9) / factor
    rounded = -rounded if value < 0 else rounded
    text = f"{rounded:.{decimals}f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def format_length(inches: float, unit: str) -> str:
    """144 in → "12 ft" / "366 cm" / "3.66 m" (frontend formatLength)."""
    unit = unit if unit in INCHES_PER_UNIT else "in"
    return f"{_plain_number(from_inches(inches, unit), UNIT_PRECISION[unit])} {unit}"


def format_wall_size(width_inches: float, height_inches: float, unit: str) -> str:
    """Wall size in the customer's unit: "12 × 9 ft"."""
    unit = unit if unit in INCHES_PER_UNIT else "in"
    precision = UNIT_PRECISION[unit]
    w = _plain_number(from_inches(width_inches, unit), precision)
    h = _plain_number(from_inches(height_inches, unit), precision)
    return f"{w} × {h} {unit}"


def _close(a: float, b: float, tolerance: float = 0.01) -> bool:
    return abs(a - b) <= tolerance


# ------------------------------ Validators ----------------------------------
# For Pydantic AfterValidator. Messages never repeat the submitted value.


def check_frame_size_id(value: str) -> str:
    if value not in _SIZES:
        raise ValueError("Unknown frame size; see GET /catalog frame_sizes")
    return value


def check_finish_id(value: str) -> str:
    if value not in _FINISHES:
        raise ValueError("Unknown frame finish; see GET /catalog frame_finishes")
    return value


def check_mount_colour_id(value: str) -> str:
    if value not in _MOUNTS:
        raise ValueError("Unknown mount colour; see GET /catalog mount_colors")
    return value


def check_paint_shade_id(value: str) -> str:
    if value not in _PAINTS:
        raise ValueError("Unknown paint shade; see GET /catalog paint_shades")
    return value


def check_layout_style(value: str) -> str:
    norm = normalize_layout(value)
    if norm not in LAYOUT_STYLE_IDS:
        raise ValueError("Unknown layout style; expected grid, salon, centre or row")
    return norm


def check_layout_type(value: str) -> str:
    norm = normalize_layout(value)
    if norm != "custom" and norm not in LAYOUT_STYLE_IDS:
        raise ValueError("Unknown layout type; expected custom, grid, salon, centre or row")
    return norm


# Pydantic field types for catalog references (shared by the design, quote and geometry schemas).
FrameSizeId = Annotated[str, AfterValidator(check_frame_size_id)]
FinishId = Annotated[str, AfterValidator(check_finish_id)]
MountColourId = Annotated[str, AfterValidator(check_mount_colour_id)]
PaintShadeId = Annotated[str, AfterValidator(check_paint_shade_id)]
LayoutStyleId = Annotated[str, AfterValidator(check_layout_style)]
LayoutTypeId = Annotated[str, AfterValidator(check_layout_type)]

"""Authoritative 2D layout validation and collision detection engine.

Validates layout bounds, 2D AABB intersections, wall safe margins, and furniture clearance.
Follows EP-GEO-01 specification where collisions return HTTP 200 with is_valid=False.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from app.modules.catalog import RULES
from app.modules.geometry.rect import Rect, bounds, overlaps

# Positions arrive rounded (e.g. to 2 dp); a frame exactly on the margin must still pass.
BOUNDARY_TOLERANCE_IN = 0.01


@dataclass(frozen=True, slots=True)
class ValidationError:
    code: str
    message: str
    item_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ValidationWarning:
    code: str
    message: str


@dataclass(frozen=True, slots=True)
class ValidationResult:
    is_valid: bool
    bounding_box: Rect
    wall_coverage_percentage: float
    errors: list[ValidationError]
    warnings: list[ValidationWarning]
    calculated_items: list[dict[str, Any]]


def validate_placed_frames(
    wall_w: float,
    wall_h: float,
    frames: Sequence[dict[str, Any]],
    margin_in: float = RULES.wall_margin_inches,
    has_sofa: bool = False,
    min_bottom_in: float | None = None,
) -> ValidationResult:
    """Authoritative validation of user-placed or engine-placed frames on a wall.

    Args:
        wall_w: Wall width in inches
        wall_h: Wall height in inches
        frames: List of dicts with:
            - item_id: str
            - outer_x_inches: float
            - outer_y_inches: float
            - outer_width_inches: float
            - outer_height_inches: float
        margin_in: Minimum safe margin from the sides and the ceiling
        has_sofa: Whether the reference sofa (and its clearance) is shown
        min_bottom_in: Lowest point above the floor; defaults to the planner rule
            (12 in, or above the sofa plus clearance), exactly like the frontend fit check
    """
    if min_bottom_in is None:
        min_bottom_in = RULES.min_bottom(has_sofa)

    errors: list[ValidationError] = []
    warnings: list[ValidationWarning] = []
    calculated_items: list[dict[str, Any]] = []

    rects: list[tuple[str, Rect]] = []

    # 1. Parse and validate dimension sanity
    for f in frames:
        item_id = str(f.get("item_id", ""))
        x = float(f.get("outer_x_inches", 0.0))
        y = float(f.get("outer_y_inches", 0.0))
        w = float(f.get("outer_width_inches", 0.0))
        h = float(f.get("outer_height_inches", 0.0))

        if w <= 0.0 or h <= 0.0:
            errors.append(
                ValidationError(
                    code="GEOMETRY_INVALID_DIMENSIONS",
                    message=f"Frame '{item_id}' has invalid dimensions (width: {w}, height: {h}).",
                    item_ids=[item_id],
                )
            )
            continue

        r = Rect(x=x, y=y, w=w, h=h)
        rects.append((item_id, r))
        calculated_items.append(
            {
                "item_id": item_id,
                "outer_x_inches": round(x, 2),
                "outer_y_inches": round(y, 2),
                "outer_width_inches": round(w, 2),
                "outer_height_inches": round(h, 2),
            }
        )

    # 2. Check 2D AABB Collisions between any pair of frames
    collision_pairs: set[tuple[str, str]] = set()
    for i in range(len(rects)):
        id_i, rect_i = rects[i]
        for j in range(i + 1, len(rects)):
            id_j, rect_j = rects[j]
            if overlaps(rect_i, rect_j):
                pair = tuple(sorted([id_i, id_j]))
                if pair not in collision_pairs:
                    collision_pairs.add(pair)
                    errors.append(
                        ValidationError(
                            code="GEOMETRY_COLLISION_DETECTED",
                            message=f"Frames '{id_i}' and '{id_j}' overlap on the wall.",
                            item_ids=[id_i, id_j],
                        )
                    )

    # 3. Check Wall Boundary Violations
    all_rects = [r for _, r in rects]
    arr_bounds = bounds(all_rects)

    for item_id, r in rects:
        if (
            r.x < margin_in - BOUNDARY_TOLERANCE_IN
            or r.right > wall_w - margin_in + BOUNDARY_TOLERANCE_IN
            or r.y < margin_in - BOUNDARY_TOLERANCE_IN
            or r.bottom > wall_h - min_bottom_in + BOUNDARY_TOLERANCE_IN
        ):
            errors.append(
                ValidationError(
                    code="GEOMETRY_OUT_OF_BOUNDS",
                    message=(
                        f"Frame '{item_id}' extends beyond the safe wall "
                        "boundaries or furniture clearance."
                    ),
                    item_ids=[item_id],
                )
            )

    # 4. Coverage calculation & warnings
    wall_area = wall_w * wall_h
    total_frame_area = sum(r.w * r.h for _, r in rects)
    coverage_pct = round((total_frame_area / wall_area * 100.0) if wall_area > 0 else 0.0, 2)

    if coverage_pct < 5.0 and len(rects) > 0:
        warnings.append(
            ValidationWarning(
                code="LOW_COVERAGE",
                message="The arrangement covers less than 5% of the wall surface.",
            )
        )

    if arr_bounds.w > (wall_w - 2.0 * margin_in) + 1e-4:
        warnings.append(
            ValidationWarning(
                code="TOO_WIDE",
                message="The overall arrangement width exceeds the safe wall span.",
            )
        )

    is_valid = len(errors) == 0

    return ValidationResult(
        is_valid=is_valid,
        bounding_box=arr_bounds,
        wall_coverage_percentage=coverage_pct,
        errors=errors,
        warnings=warnings,
        calculated_items=calculated_items if is_valid else [],
    )

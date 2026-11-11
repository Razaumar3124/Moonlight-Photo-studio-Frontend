"""Scene assembly, eye-level alignment, boundary clamping, and layout suggestion ranking.

Mirrors the frontend scene.ts mathematical logic.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.modules.geometry.layouts import (
    LAYOUT_ENGINES,
    LAYOUT_STYLES,
    LayoutInput,
    LayoutStyle,
)
from app.modules.geometry.rect import (
    Rect,
    Size,
    area,
    bounds,
    overlaps,
    translate,
)

EYE_LEVEL_FROM_FLOOR_IN = 57.0
DEFAULT_WALL_MARGIN_IN = 6.0
DEFAULT_MIN_BOTTOM_IN = 24.0
SOFA_TOP_FROM_FLOOR_IN = 32.0
SOFA_CLEARANCE_IN = 8.0
VARIANT_COUNT = 3


@dataclass(frozen=True, slots=True)
class FrameGeometry:
    """Calculated dimensions of a picture frame on the wall."""

    item_id: str
    opening_w: float
    opening_h: float
    mat_in: float
    profile_in: float
    outer_w: float
    outer_h: float


def compute_frame_geometry(
    item_id: str,
    opening_w: float,
    opening_h: float,
    mat_in: float = 0.0,
    profile_in: float = 1.0,
) -> FrameGeometry:
    """Compute frame outer dimensions from photo opening, mat width, and molding profile."""
    outer_w = opening_w + 2.0 * (mat_in + profile_in)
    outer_h = opening_h + 2.0 * (mat_in + profile_in)
    return FrameGeometry(
        item_id=item_id,
        opening_w=opening_w,
        opening_h=opening_h,
        mat_in=mat_in,
        profile_in=profile_in,
        outer_w=outer_w,
        outer_h=outer_h,
    )


@dataclass(frozen=True, slots=True)
class PlacedFrame:
    """Frame with calculated wall coordinates."""

    item_id: str
    outer_rect: Rect
    inner_rect: Rect
    photo_rect: Rect


@dataclass(frozen=True, slots=True)
class SceneWarning:
    code: Literal["TOO_WIDE", "TOO_TALL", "OVERLAP", "LOW_COVERAGE"]
    message: str


@dataclass(frozen=True, slots=True)
class Scene:
    """Complete assembled gallery wall scene."""

    wall_w: float
    wall_h: float
    style: LayoutStyle
    variant: int
    seed: int
    frames: list[PlacedFrame]
    arrangement: Rect
    eye_level_y: float
    sofa_top_y: float | None
    fits: bool
    coverage: float
    warnings: list[SceneWarning]


def build_scene(
    wall_w: float,
    wall_h: float,
    frames: Sequence[FrameGeometry],
    style: LayoutStyle = "grid",
    gap: float = 3.0,
    variant: int = 0,
    seed: int = 0,
    margin_in: float = DEFAULT_WALL_MARGIN_IN,
    has_sofa: bool = False,
    eye_level_in: float = EYE_LEVEL_FROM_FLOOR_IN,
) -> Scene:
    """Construct a full gallery wall scene positioned at eye-level with clearances."""
    if style not in LAYOUT_ENGINES:
        style = "grid"

    # Wall clearances
    sofa_h = SOFA_TOP_FROM_FLOOR_IN + SOFA_CLEARANCE_IN
    sofa_clearance = sofa_h if has_sofa else DEFAULT_MIN_BOTTOM_IN
    min_bottom = max(DEFAULT_MIN_BOTTOM_IN, sofa_clearance)
    max_w = max(0.0, wall_w - 2.0 * margin_in)
    max_h = max(0.0, wall_h - margin_in - min_bottom)

    # 1. Run deterministic layout solver
    sizes = [Size(w=f.outer_w, h=f.outer_h) for f in frames]
    layout_fn = LAYOUT_ENGINES[style]
    rects = layout_fn(
        LayoutInput(
            sizes=sizes,
            gap=gap,
            max_width=max_w,
            max_height=max_h,
            variant=variant,
            seed=seed,
        )
    )

    arr_bounds = bounds(rects)

    # 2. Position arrangement relative to eye level and wall center
    eye_level_y = wall_h - eye_level_in
    target_x = (wall_w - arr_bounds.w) / 2.0
    target_y = eye_level_y - arr_bounds.h / 2.0

    # Clamp vertically within safe boundary
    max_y = wall_h - min_bottom - arr_bounds.h
    target_y = max(margin_in, min(target_y, max_y))

    # Shift all rects to wall coordinate system
    shift_x = target_x - arr_bounds.x
    shift_y = target_y - arr_bounds.y
    placed_rects = [translate(r, shift_x, shift_y) for r in rects]
    final_arrangement = bounds(placed_rects)

    # 3. Assemble PlacedFrame instances with inner/photo bounds
    placed_frames: list[PlacedFrame] = []
    for f, r in zip(frames, placed_rects, strict=False):
        inner_x = r.x + f.profile_in
        inner_y = r.y + f.profile_in
        inner_w = max(0.0, r.w - 2.0 * f.profile_in)
        inner_h = max(0.0, r.h - 2.0 * f.profile_in)
        inner_rect = Rect(x=inner_x, y=inner_y, w=inner_w, h=inner_h)

        photo_x = inner_x + f.mat_in
        photo_y = inner_y + f.mat_in
        photo_w = f.opening_w
        photo_h = f.opening_h
        photo_rect = Rect(x=photo_x, y=photo_y, w=photo_w, h=photo_h)

        placed_frames.append(
            PlacedFrame(
                item_id=f.item_id,
                outer_rect=r,
                inner_rect=inner_rect,
                photo_rect=photo_rect,
            )
        )

    # 4. Invariants & validation warnings
    warnings: list[SceneWarning] = []
    too_wide = final_arrangement.w > max_w + 1e-6
    too_tall = (final_arrangement.y < margin_in - 1e-6) or (
        final_arrangement.bottom > wall_h - min_bottom + 1e-6
    )

    if too_wide:
        warnings.append(
            SceneWarning(
                code="TOO_WIDE",
                message=(
                    "The arrangement is wider than the wall allows. "
                    "Try smaller frames or a narrower gap."
                ),
            )
        )
    if too_tall:
        warnings.append(
            SceneWarning(
                code="TOO_TALL",
                message="The arrangement is taller than the wall allows.",
            )
        )

    has_overlap = any(
        overlaps(placed_rects[i], placed_rects[j])
        for i in range(len(placed_rects))
        for j in range(i + 1, len(placed_rects))
    )
    if has_overlap:
        warnings.append(SceneWarning(code="OVERLAP", message="Some frames overlap on the wall."))

    wall_surface = wall_w * wall_h
    total_frame_area = sum(area(r) for r in placed_rects)
    coverage = total_frame_area / wall_surface if wall_surface > 0 else 0.0

    if coverage < 0.05 and len(frames) > 0:
        warnings.append(
            SceneWarning(
                code="LOW_COVERAGE",
                message=(
                    "The arrangement covers very little of the wall. "
                    "Larger frames will look more intentional."
                ),
            )
        )

    fits = (not too_wide) and (not too_tall) and (not has_overlap)

    return Scene(
        wall_w=wall_w,
        wall_h=wall_h,
        style=style,
        variant=variant,
        seed=seed,
        frames=placed_frames,
        arrangement=final_arrangement,
        eye_level_y=eye_level_y,
        sofa_top_y=(wall_h - SOFA_TOP_FROM_FLOOR_IN) if has_sofa else None,
        fits=fits,
        coverage=coverage,
        warnings=warnings,
    )


@dataclass(frozen=True, slots=True)
class LayoutSuggestion:
    style: LayoutStyle
    variant: int
    scene: Scene
    score: float


def suggest_layouts(
    wall_w: float,
    wall_h: float,
    frames: Sequence[FrameGeometry],
    gap: float = 3.0,
    seed: int = 0,
    margin_in: float = DEFAULT_WALL_MARGIN_IN,
    has_sofa: bool = False,
    eye_level_in: float = EYE_LEVEL_FROM_FLOOR_IN,
) -> list[LayoutSuggestion]:
    """Evaluate every layout style x variant for the given frames and rank them.

    Scoring prioritizes fitting the wall, achieving ~25% coverage, and matching proportions.
    """
    suggestions: list[LayoutSuggestion] = []
    free_w = wall_w - 2.0 * margin_in
    free_h = (
        wall_h
        - margin_in
        - (SOFA_TOP_FROM_FLOOR_IN + SOFA_CLEARANCE_IN if has_sofa else DEFAULT_MIN_BOTTOM_IN)
    )
    target_aspect = (free_w / free_h) if free_h > 0 else 1.0

    for style in LAYOUT_STYLES:
        for variant in range(VARIANT_COUNT):
            scene = build_scene(
                wall_w=wall_w,
                wall_h=wall_h,
                frames=frames,
                style=style,
                gap=gap,
                variant=variant,
                seed=seed,
                margin_in=margin_in,
                has_sofa=has_sofa,
                eye_level_in=eye_level_in,
            )
            arr = scene.arrangement
            arr_aspect = (arr.w / arr.h) if arr.h > 0 else 1.0
            aspect_miss = abs(math.log(arr_aspect / target_aspect))
            coverage_miss = abs(scene.coverage - 0.25)

            score = (
                (0.0 if scene.fits else 10.0)
                + coverage_miss * 2.0
                + aspect_miss * 0.6
                + variant * 0.01
            )

            suggestions.append(
                LayoutSuggestion(
                    style=style,
                    variant=variant,
                    scene=scene,
                    score=score,
                )
            )

    suggestions.sort(key=lambda s: s.score)
    return suggestions

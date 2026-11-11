"""Aesthetic scoring, balance metrics, and layout diversity / similarity checks.

Used to guarantee that 'Redesign' delivers a meaningfully different layout
and 'Regenerate' produces fresh variations without duplicate arrangements.
"""

from collections.abc import Sequence

from app.modules.geometry.rect import Rect, bounds


def calculate_visual_balance(rects: Sequence[Rect]) -> float:
    """Calculate horizontal visual balance score around the central axis [0.0 - 1.0].

    1.0 = perfect left-right symmetry in frame area.
    """
    if not rects:
        return 1.0

    b = bounds(rects)
    center_x = b.center_x
    left_area = sum(r.w * r.h for r in rects if r.center_x < center_x)
    right_area = sum(r.w * r.h for r in rects if r.center_x > center_x)

    total = left_area + right_area
    if total <= 0:
        return 1.0

    diff = abs(left_area - right_area)
    return max(0.0, 1.0 - (diff / total))


def layout_similarity(layout_a: Sequence[Rect], layout_b: Sequence[Rect]) -> float:
    """Compute structural similarity between two layouts [0.0 - 1.0].

    Based on normalized center-point distances and relative bounding shapes.
    1.0 means identical positions; 0.0 means completely different structure.
    """
    if len(layout_a) != len(layout_b) or not layout_a:
        return 0.0

    b_a = bounds(layout_a)

    # Normalize sizes
    diag_a = max(1.0, (b_a.w**2 + b_a.h**2) ** 0.5)

    distances: list[float] = []
    for ra, rb in zip(layout_a, layout_b, strict=False):
        # Distance between centers normalized by layout diagonal
        dist = ((ra.center_x - rb.center_x) ** 2 + (ra.center_y - rb.center_y) ** 2) ** 0.5
        distances.append(min(1.0, dist / diag_a))

    mean_dist = sum(distances) / len(distances)
    return max(0.0, 1.0 - mean_dist)


def is_meaningfully_different(
    layout_a: Sequence[Rect], layout_b: Sequence[Rect], threshold: float = 0.85
) -> bool:
    """True if layout_b is sufficiently distinct from layout_a (similarity < threshold)."""
    return layout_similarity(layout_a, layout_b) < threshold

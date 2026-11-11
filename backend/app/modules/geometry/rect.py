"""2D Rectangle geometry utilities, bounding box calculations, and collision detection.

Ported from frontend TypeScript geometry engine (`rect.ts`).
Uses inch units consistently with floating point precision.
"""

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Size:
    """2D rectangular dimensions in inches."""

    w: float
    h: float


@dataclass(frozen=True, slots=True)
class Rect:
    """Positioned 2D axis-aligned bounding box (AABB) in inches."""

    x: float
    y: float
    w: float
    h: float

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h

    @property
    def center_x(self) -> float:
        return self.x + self.w / 2.0

    @property
    def center_y(self) -> float:
        return self.y + self.h / 2.0


def area(item: Size | Rect) -> float:
    """Calculate rectangular surface area."""
    return max(0.0, item.w) * max(0.0, item.h)


def bounds(rects: Sequence[Rect]) -> Rect:
    """Bounding box containing every rect in the sequence.

    Returns Rect(0, 0, 0, 0) if sequence is empty.
    """
    if not rects:
        return Rect(0.0, 0.0, 0.0, 0.0)

    min_x = min(r.x for r in rects)
    min_y = min(r.y for r in rects)
    max_x = max(r.x + r.w for r in rects)
    max_y = max(r.y + r.h for r in rects)

    return Rect(x=min_x, y=min_y, w=max_x - min_x, h=max_y - min_y)


def conflicts(a: Rect, b: Rect, gap: float = 0.0, eps: float = 1e-6) -> bool:
    """True if rects `a` and `b` overlap or are closer than `gap` inches.

    Uses epsilon tolerance to prevent false positives when edges align cleanly.
    """
    return (
        a.x < b.x + b.w + gap - eps
        and a.x + a.w + gap - eps > b.x
        and a.y < b.y + b.h + gap - eps
        and a.y + a.h + gap - eps > b.y
    )


def overlaps(a: Rect, b: Rect, eps: float = 1e-4) -> bool:
    """True if rects `a` and `b` overlap in 2D space (excluding mere border contact)."""
    return (
        a.x < b.x + b.w - eps
        and a.x + a.w > b.x + eps
        and a.y < b.y + b.h - eps
        and a.y + a.h > b.y + eps
    )


def inset(rect: Rect, dx: float, dy: float) -> Rect:
    """Shrink a rectangle by dx along horizontal sides and dy along vertical sides."""
    return Rect(
        x=rect.x + dx,
        y=rect.y + dy,
        w=max(0.0, rect.w - 2.0 * dx),
        h=max(0.0, rect.h - 2.0 * dy),
    )


def translate(rect: Rect, dx: float, dy: float) -> Rect:
    """Translate rectangle by dx and dy."""
    return Rect(x=rect.x + dx, y=rect.y + dy, w=rect.w, h=rect.h)


def normalize(rects: Sequence[Rect]) -> list[Rect]:
    """Translate rects as a group so the overall bounding box top-left starts at (0, 0)."""
    if not rects:
        return []
    b = bounds(rects)
    return [translate(r, -b.x, -b.y) for r in rects]

"""Deterministic gallery wall layout algorithms ported from frontend layouts.ts.

All algorithms take frame outer sizes (in display order) and return one Rect
per frame relative to the arrangement's top-left (0, 0).
Guaranteed collision-free, deterministic for a given (seed, variant).
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from app.modules.geometry.random import create_rng, mix_seed, shuffle
from app.modules.geometry.rect import (
    Rect,
    Size,
    area,
    bounds,
    conflicts,
    normalize,
)

LayoutStyle = Literal["grid", "salon", "centre", "row"]
LAYOUT_STYLES: list[LayoutStyle] = ["grid", "salon", "centre", "row"]


@dataclass(frozen=True, slots=True)
class LayoutInput:
    """Input parameters for deterministic layout solvers."""

    sizes: Sequence[Size]
    gap: float
    max_width: float
    max_height: float
    variant: int = 0
    seed: int = 0


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


# ================================== Grid ==================================


def grid_layout(inp: LayoutInput) -> list[Rect]:
    """Uniform rows x columns layout.

    Column count is selected to best match free wall area aspect ratio.
    Columns take their widest frame, rows their tallest; frames are centered
    in their cell and a short last row is centered.
    """
    n = len(inp.sizes)
    if n == 0:
        return []

    avg_w = _mean([s.w for s in inp.sizes])
    avg_h = _mean([s.h for s in inp.sizes])
    target = math.sqrt(inp.max_width / inp.max_height) if inp.max_height > 0 else 1.0

    ranked: list[tuple[float, int]] = []
    for cols in range(1, n + 1):
        rows = math.ceil(n / cols)
        w = cols * avg_w + (cols - 1) * inp.gap
        h = rows * avg_h + (rows - 1) * inp.gap
        empty = rows * cols - n
        overflow = ((w - inp.max_width) / inp.max_width if w > inp.max_width else 0.0) + (
            (h - inp.max_height) / inp.max_height if h > inp.max_height else 0.0
        )
        aspect_ratio = (w / h) if h > 0 else 1.0
        score = abs(math.log(aspect_ratio / target)) + empty * 0.45 + overflow * 4.0
        ranked.append((score, cols))

    ranked.sort(key=lambda x: x[0])
    chosen_cols = ranked[inp.variant % min(3, len(ranked))][1]
    rows = math.ceil(n / chosen_cols)

    col_w: list[float] = [
        max(
            [s.w for i, s in enumerate(inp.sizes) if i % chosen_cols == c],
            default=avg_w,
        )
        for c in range(chosen_cols)
    ]
    row_h: list[float] = [
        max(
            [s.h for s in inp.sizes[r * chosen_cols : r * chosen_cols + chosen_cols]],
            default=avg_h,
        )
        for r in range(rows)
    ]
    full_width = sum(col_w) + (chosen_cols - 1) * inp.gap

    rects: list[Rect] = []
    y = 0.0
    for r in range(rows):
        row_sizes = inp.sizes[r * chosen_cols : r * chosen_cols + chosen_cols]
        is_short = len(row_sizes) < chosen_cols
        widths = [s.w for s in row_sizes] if is_short else col_w
        row_width = sum(widths[: len(row_sizes)]) + (len(row_sizes) - 1) * inp.gap
        x = (full_width - row_width) / 2.0 if is_short else 0.0

        for c, s in enumerate(row_sizes):
            cw = widths[c]
            rects.append(
                Rect(
                    x=x + (cw - s.w) / 2.0,
                    y=y + (row_h[r] - s.h) / 2.0,
                    w=s.w,
                    h=s.h,
                )
            )
            x += cw + inp.gap
        y += row_h[r] + inp.gap

    return normalize(rects)


# =================================== Row ===================================


def row_layout(inp: LayoutInput) -> list[Rect]:
    """Frames side by side on a shared center line (or top/bottom aligned).

    Wraps into balanced rows when total width exceeds wall width.
    """
    n = len(inp.sizes)
    if n == 0:
        return []

    indices = list(range(n))
    row_aligns = ["center", "top", "bottom"]
    align = row_aligns[inp.variant % len(row_aligns)]

    if inp.variant >= len(row_aligns):
        rng = create_rng(mix_seed(inp.seed, inp.variant))
        order = shuffle(indices, rng)
    else:
        order = indices

    total = sum(s.w for s in inp.sizes) + (n - 1) * inp.gap
    line_count = min(n, max(1, math.ceil(total / max(inp.max_width, 1.0))))
    target_line = total / line_count

    lines: list[list[int]] = [[]]
    line_width = 0.0

    for i in order:
        w = inp.sizes[i].w
        current = lines[-1]
        exceeds_line = line_width + inp.gap + w > target_line + w / 2.0
        if current and exceeds_line and len(lines) < line_count:
            lines.append([i])
            line_width = w
        else:
            current.append(i)
            line_width += (inp.gap if len(current) > 1 else 0.0) + w

    widths = [sum(inp.sizes[i].w for i in line) + (len(line) - 1) * inp.gap for line in lines]
    full_width = max(widths, default=0.0)
    rects: list[Rect] = [Rect(0.0, 0.0, 0.0, 0.0)] * n

    y = 0.0
    for li, line in enumerate(lines):
        line_h = max(inp.sizes[i].h for i in line)
        x = (full_width - widths[li]) / 2.0
        for i in line:
            s = inp.sizes[i]
            if align == "top":
                dy = 0.0
            elif align == "bottom":
                dy = line_h - s.h
            else:
                dy = (line_h - s.h) / 2.0
            rects[i] = Rect(x=x, y=y + dy, w=s.w, h=s.h)
            x += s.w + inp.gap
        y += line_h + inp.gap

    return normalize(rects)


# ================================= Centre =================================


def centre_layout(inp: LayoutInput) -> list[Rect]:
    """Largest focal frame is anchored at the origin.

    Remaining frames fill alternating columns on left and right sides,
    stacked up to the focal frame's height and vertically centered to balance visual weight.
    """
    n = len(inp.sizes)
    if n == 0:
        return []

    by_area = sorted(range(n), key=lambda i: area(inp.sizes[i]), reverse=True)
    hero = by_area[0]
    others = by_area[1:]

    if inp.variant > 0:
        rng = create_rng(mix_seed(inp.seed, inp.variant))
        others = shuffle(others, rng)

    inner_align = inp.variant % 2 == 1

    hero_size = inp.sizes[hero]
    max_stack = max([hero_size.h] + [inp.sizes[i].h for i in others])

    @dataclass
    class Column:
        items: list[int]
        height: float
        width: float

    sides: dict[str, list[Column]] = {"left": [], "right": []}
    side_area: dict[str, float] = {"left": 0.0, "right": 0.0}

    for i in others:
        s = inp.sizes[i]
        side = "left" if side_area["left"] <= side_area["right"] else "right"
        cols = sides[side]
        last = cols[-1] if cols else None

        if last and (last.height + inp.gap + s.h <= max_stack + 1e-6):
            last.items.append(i)
            last.height += inp.gap + s.h
            last.width = max(last.width, s.w)
        else:
            cols.append(Column(items=[i], height=s.h, width=s.w))

        side_area[side] += area(s)

    rects: list[Rect] = [Rect(0.0, 0.0, 0.0, 0.0)] * n
    rects[hero] = Rect(
        x=-hero_size.w / 2.0,
        y=-hero_size.h / 2.0,
        w=hero_size.w,
        h=hero_size.h,
    )

    for side in ("left", "right"):
        edge = -hero_size.w / 2.0 - inp.gap if side == "left" else hero_size.w / 2.0 + inp.gap
        for col in sides[side]:
            col_x = edge - col.width if side == "left" else edge
            y = -col.height / 2.0
            for i in col.items:
                s = inp.sizes[i]
                free = col.width - s.w
                dx = (free if side == "left" else 0.0) if inner_align else free / 2.0
                rects[i] = Rect(x=col_x + dx, y=y, w=s.w, h=s.h)
                y += s.h + inp.gap
            edge = col_x - inp.gap if side == "left" else col_x + col.width + inp.gap

    return normalize(rects)


# ================================= Salon ==================================


def salon_layout(inp: LayoutInput) -> list[Rect]:
    """Organic salon gallery layout using greedy 2D AABB adjacency packing.

    1. Largest frame placed at center.
    2. Candidates generated touching already-placed frames at exactly `gap` distance.
    3. Collision candidates dropped; best candidate picked by compactness,
       aspect ratio, and wall boundary fit.
    """
    n = len(inp.sizes)
    if n == 0:
        return []

    rng = create_rng(mix_seed(inp.seed, inp.variant, 0x5A10))
    target = inp.max_width / inp.max_height if inp.max_height > 0 else 1.0
    total_area = sum(area(s) for s in inp.sizes)
    scale = math.sqrt(total_area) if total_area > 0 else 1.0

    by_area = sorted(range(n), key=lambda i: area(inp.sizes[i]), reverse=True)
    if inp.variant == 0:
        order = by_area
    else:
        order = [by_area[0]] + shuffle(by_area[1:], rng)

    jitter = 0.02 if inp.variant == 0 else 0.12

    placed: list[Rect] = []
    rects: list[Rect] = [Rect(0.0, 0.0, 0.0, 0.0)] * n

    first_idx = order[0]
    first = inp.sizes[first_idx]
    first_rect = Rect(x=-first.w / 2.0, y=-first.h / 2.0, w=first.w, h=first.h)
    placed.append(first_rect)
    rects[first_idx] = first_rect

    for idx in order[1:]:
        s = inp.sizes[idx]
        best_candidate: Rect | None = None
        best_score = float("inf")

        for p in placed:
            xs = [p.x, p.x + (p.w - s.w) / 2.0, p.x + p.w - s.w]
            ys = [p.y, p.y + (p.h - s.h) / 2.0, p.y + p.h - s.h]

            candidates: list[Rect] = [
                *[Rect(x=p.x + p.w + inp.gap, y=y, w=s.w, h=s.h) for y in ys],  # right
                *[Rect(x=p.x - inp.gap - s.w, y=y, w=s.w, h=s.h) for y in ys],  # left
                *[Rect(x=x, y=p.y + p.h + inp.gap, w=s.w, h=s.h) for x in xs],  # below
                *[Rect(x=x, y=p.y - inp.gap - s.h, w=s.w, h=s.h) for x in xs],  # above
            ]

            for c in candidates:
                if any(conflicts(c, q, inp.gap) for q in placed):
                    continue

                b = bounds([*placed, c])
                area_score = (b.w * b.h) / total_area if total_area > 0 else 1.0
                aspect = abs(math.log((b.w / b.h) / target)) if b.h > 0 else 0.0
                centre_dist = math.hypot(c.x + c.w / 2.0, c.y + c.h / 2.0) / scale
                overflow = (
                    (b.w - inp.max_width) / inp.max_width if b.w > inp.max_width else 0.0
                ) + ((b.h - inp.max_height) / inp.max_height if b.h > inp.max_height else 0.0)

                score = (
                    area_score + 0.6 * aspect + 0.25 * centre_dist + 6.0 * overflow + rng() * jitter
                )

                if score < best_score:
                    best_score = score
                    best_candidate = c

        if best_candidate is not None:
            chosen = best_candidate
        else:
            # Fallback to outer right edge if packed
            current_bounds = bounds(placed)
            chosen = Rect(x=current_bounds.x + current_bounds.w + inp.gap, y=0.0, w=s.w, h=s.h)

        placed.append(chosen)
        rects[idx] = chosen

    return normalize(rects)


LAYOUT_ENGINES = {
    "grid": grid_layout,
    "row": row_layout,
    "centre": centre_layout,
    "salon": salon_layout,
}

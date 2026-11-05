/** Geometry primitives. All values are inches; origin top-left, y grows downward (API convention). */

export interface Size {
  w: number
  h: number
}

export interface Rect extends Size {
  x: number
  y: number
}

/** Tolerance for float comparisons (1/1000 inch). */
export const EPS = 1e-3

export function bounds(rects: readonly Rect[]): Rect {
  if (rects.length === 0) return { x: 0, y: 0, w: 0, h: 0 }
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const r of rects) {
    minX = Math.min(minX, r.x)
    minY = Math.min(minY, r.y)
    maxX = Math.max(maxX, r.x + r.w)
    maxY = Math.max(maxY, r.y + r.h)
  }
  return { x: minX, y: minY, w: maxX - minX, h: maxY - minY }
}

export function translate(rects: readonly Rect[], dx: number, dy: number): Rect[] {
  return rects.map((r) => ({ ...r, x: r.x + dx, y: r.y + dy }))
}

/** Move rects so their bounding box starts at (0, 0). */
export function normalize(rects: readonly Rect[]): Rect[] {
  const b = bounds(rects)
  return translate(rects, -b.x, -b.y)
}

/**
 * True if the rects are closer than `gap` (i.e. they overlap once each is grown by gap/2).
 * Rects exactly `gap` apart do NOT conflict.
 */
export function conflicts(a: Rect, b: Rect, gap = 0): boolean {
  return (
    a.x < b.x + b.w + gap - EPS &&
    b.x < a.x + a.w + gap - EPS &&
    a.y < b.y + b.h + gap - EPS &&
    b.y < a.y + a.h + gap - EPS
  )
}

export function contains(outer: Rect, inner: Rect): boolean {
  return (
    inner.x >= outer.x - EPS &&
    inner.y >= outer.y - EPS &&
    inner.x + inner.w <= outer.x + outer.w + EPS &&
    inner.y + inner.h <= outer.y + outer.h + EPS
  )
}

export function inset(r: Rect, by: number): Rect {
  return { x: r.x + by, y: r.y + by, w: Math.max(0, r.w - 2 * by), h: Math.max(0, r.h - 2 * by) }
}

export const area = (s: Size) => s.w * s.h

import { createRng, mixSeed, shuffle } from './random'
import { area, bounds, conflicts, normalize, type Rect, type Size } from './rect'

/**
 * Layout algorithms. Each takes the frames' OUTER sizes (in display order) and returns one
 * rect per frame, in the same order, relative to the arrangement's own top-left (0, 0).
 * They're pure and deterministic for a given (seed, variant): no DOM, no React.
 */

export type LayoutStyle = 'grid' | 'salon' | 'centre' | 'row'

export interface LayoutInput {
  sizes: readonly Size[]
  /** Minimum clear space between frames, inches. */
  gap: number
  /** Space available on the wall for the arrangement (inside margins), inches. */
  maxWidth: number
  maxHeight: number
  /** 0 = the "best" arrangement; higher values are alternatives. */
  variant: number
  seed: number
}

export type LayoutFn = (input: LayoutInput) => Rect[]

const sum = (xs: readonly number[]) => xs.reduce((a, b) => a + b, 0)
const mean = (xs: readonly number[]) => (xs.length ? sum(xs) / xs.length : 0)
const at = <T>(xs: readonly T[], i: number): T => {
  const v = xs[i]
  if (v === undefined) throw new Error(`index ${i} out of range`)
  return v
}

/* ================================== Grid ================================== */

/**
 * Uniform rows × columns. The column count is chosen so the grid's aspect ratio best matches
 * the free wall area (variants try the 2nd/3rd best). Columns take their widest frame, rows
 * their tallest; frames are centred in their cell and a short last row is centred.
 */
export const gridLayout: LayoutFn = ({ sizes, gap, maxWidth, maxHeight, variant }) => {
  const n = sizes.length
  if (n === 0) return []
  const avgW = mean(sizes.map((s) => s.w))
  const avgH = mean(sizes.map((s) => s.h))
  // Aim between square and the free area's shape: a 3:2 wall → ~1.22:1 grid. Matching the wall
  // exactly produces long, thin grids that read as "wallpaper" rather than a gallery.
  const target = Math.sqrt(maxWidth / maxHeight)

  const ranked = Array.from({ length: n }, (_, i) => i + 1)
    .map((cols) => {
      const rows = Math.ceil(n / cols)
      const w = cols * avgW + (cols - 1) * gap
      const h = rows * avgH + (rows - 1) * gap
      // Every empty cell is a visible hole; complete grids win unless the shape is far off.
      const empty = rows * cols - n
      const overflow =
        (w > maxWidth ? (w - maxWidth) / maxWidth : 0) + (h > maxHeight ? (h - maxHeight) / maxHeight : 0)
      return { cols, score: Math.abs(Math.log(w / h / target)) + empty * 0.45 + overflow * 4 }
    })
    .sort((a, b) => a.score - b.score)

  const cols = at(ranked, variant % Math.min(3, ranked.length)).cols
  const rows = Math.ceil(n / cols)

  const colW = Array.from({ length: cols }, (_, c) =>
    Math.max(...sizes.filter((_size, i) => i % cols === c).map((s) => s.w)),
  )
  const rowH = Array.from({ length: rows }, (_, r) =>
    Math.max(...sizes.slice(r * cols, r * cols + cols).map((s) => s.h)),
  )
  const fullWidth = sum(colW) + (cols - 1) * gap

  const rects: Rect[] = []
  let y = 0
  for (let r = 0; r < rows; r++) {
    const rowSizes = sizes.slice(r * cols, r * cols + cols)
    const isShort = rowSizes.length < cols
    // A short last row uses its own widths and is centred under the full rows.
    const widths = isShort ? rowSizes.map((s) => s.w) : colW
    const rowWidth = sum(widths.slice(0, rowSizes.length)) + (rowSizes.length - 1) * gap
    let x = isShort ? (fullWidth - rowWidth) / 2 : 0
    rowSizes.forEach((s, c) => {
      const cw = at(widths, c)
      rects.push({ x: x + (cw - s.w) / 2, y: y + (at(rowH, r) - s.h) / 2, w: s.w, h: s.h })
      x += cw + gap
    })
    y += at(rowH, r) + gap
  }
  return normalize(rects)
}

/* =================================== Row =================================== */

type VAlign = 'center' | 'top' | 'bottom'
const ROW_ALIGNS: readonly VAlign[] = ['center', 'top', 'bottom']

/**
 * Frames side by side on a shared centre line (variants: aligned tops / bottoms, or a new order).
 * Wraps into balanced rows when the line would be wider than the wall.
 */
export const rowLayout: LayoutFn = ({ sizes, gap, maxWidth, variant, seed }) => {
  const n = sizes.length
  if (n === 0) return []
  const indices = Array.from({ length: n }, (_, i) => i)
  const order = variant >= ROW_ALIGNS.length ? shuffle(indices, createRng(mixSeed(seed, variant))) : indices
  const align = at(ROW_ALIGNS, variant % ROW_ALIGNS.length)

  // Fewest lines that fit, then spread frames evenly across them by width.
  const total = sum(sizes.map((s) => s.w)) + (n - 1) * gap
  const lineCount = Math.min(n, Math.max(1, Math.ceil(total / Math.max(maxWidth, 1))))
  const targetLine = total / lineCount
  const lines: number[][] = [[]]
  let lineWidth = 0
  for (const i of order) {
    const w = at(sizes, i).w
    const current = at(lines, lines.length - 1)
    if (current.length && lineWidth + gap + w > targetLine + w / 2 && lines.length < lineCount) {
      lines.push([i])
      lineWidth = w
    } else {
      current.push(i)
      lineWidth += (current.length > 1 ? gap : 0) + w
    }
  }

  const widths = lines.map((l) => sum(l.map((i) => at(sizes, i).w)) + (l.length - 1) * gap)
  const fullWidth = Math.max(...widths)
  const rects: Rect[] = new Array<Rect>(n)
  let y = 0
  lines.forEach((line, li) => {
    const lineH = Math.max(...line.map((i) => at(sizes, i).h))
    let x = (fullWidth - at(widths, li)) / 2
    for (const i of line) {
      const s = at(sizes, i)
      const dy = align === 'top' ? 0 : align === 'bottom' ? lineH - s.h : (lineH - s.h) / 2
      rects[i] = { x, y: y + dy, w: s.w, h: s.h }
      x += s.w + gap
    }
    y += lineH + gap
  })
  return normalize(rects)
}

/* ================================= Centre ================================= */

/**
 * The largest frame is the focal point. The others fill columns on alternating sides, each
 * column stacked to at most the focal frame's height and vertically centred on it, so the
 * composition stays symmetric in visual weight.
 */
export const centreLayout: LayoutFn = ({ sizes, gap, variant, seed }) => {
  const n = sizes.length
  if (n === 0) return []
  const byArea = Array.from({ length: n }, (_, i) => i).sort(
    (a, b) => area(at(sizes, b)) - area(at(sizes, a)),
  )
  const hero = at(byArea, 0)
  let others = byArea.slice(1)
  if (variant > 0) others = shuffle(others, createRng(mixSeed(seed, variant)))
  const innerAlign = variant % 2 === 1 // alternative: columns hug the focal frame

  const heroSize = at(sizes, hero)
  const maxStack = Math.max(heroSize.h, ...others.map((i) => at(sizes, i).h))
  type Column = { items: number[]; height: number; width: number }
  const sides: Record<'left' | 'right', Column[]> = { left: [], right: [] }
  const sideArea = { left: 0, right: 0 }

  for (const i of others) {
    const s = at(sizes, i)
    const side = sideArea.left <= sideArea.right ? 'left' : 'right'
    const cols = sides[side]
    const last = cols[cols.length - 1]
    if (last && last.height + gap + s.h <= maxStack + 1e-6) {
      last.items.push(i)
      last.height += gap + s.h
      last.width = Math.max(last.width, s.w)
    } else {
      cols.push({ items: [i], height: s.h, width: s.w })
    }
    sideArea[side] += area(s)
  }

  const rects: Rect[] = new Array<Rect>(n)
  rects[hero] = { x: -heroSize.w / 2, y: -heroSize.h / 2, w: heroSize.w, h: heroSize.h }

  for (const side of ['left', 'right'] as const) {
    let edge = side === 'left' ? -heroSize.w / 2 - gap : heroSize.w / 2 + gap
    for (const col of sides[side]) {
      const colX = side === 'left' ? edge - col.width : edge
      let y = -col.height / 2
      for (const i of col.items) {
        const s = at(sizes, i)
        const free = col.width - s.w
        const dx = innerAlign ? (side === 'left' ? free : 0) : free / 2
        rects[i] = { x: colX + dx, y, w: s.w, h: s.h }
        y += s.h + gap
      }
      edge = side === 'left' ? colX - gap : colX + col.width + gap
    }
  }
  return normalize(rects)
}

/* ================================= Salon ================================== */

/**
 * Organic "salon" hang via greedy adjacency packing:
 * 1. Place the largest frame at the origin.
 * 2. For each next frame, generate candidate spots touching an already-placed frame (left, right,
 *    above, below; aligned to its start, centre or end) at exactly `gap` distance.
 * 3. Drop candidates closer than `gap` to any frame, then pick the one that keeps the cluster
 *    compact, centred and close to the wall's proportions. Variants add seeded jitter and order.
 * O(n² · 12) per layout, trivial for n ≤ 16.
 */
export const salonLayout: LayoutFn = ({ sizes, gap, maxWidth, maxHeight, variant, seed }) => {
  const n = sizes.length
  if (n === 0) return []
  const rng = createRng(mixSeed(seed, variant, 0x5a10))
  const target = maxWidth / maxHeight
  const totalArea = sum(sizes.map(area))
  const scale = Math.sqrt(totalArea)

  const byArea = Array.from({ length: n }, (_, i) => i).sort(
    (a, b) => area(at(sizes, b)) - area(at(sizes, a)),
  )
  // Keep the anchor; variants reshuffle the rest so the cluster grows differently.
  const order = variant === 0 ? byArea : [at(byArea, 0), ...shuffle(byArea.slice(1), rng)]
  const jitter = variant === 0 ? 0.02 : 0.12

  const placed: Rect[] = []
  const rects: Rect[] = new Array<Rect>(n)
  const first = at(sizes, at(order, 0))
  const firstRect = { x: -first.w / 2, y: -first.h / 2, w: first.w, h: first.h }
  placed.push(firstRect)
  rects[at(order, 0)] = firstRect

  for (const idx of order.slice(1)) {
    const s = at(sizes, idx)
    let best: { rect: Rect; score: number } | null = null
    for (const p of placed) {
      const xs = [p.x, p.x + (p.w - s.w) / 2, p.x + p.w - s.w]
      const ys = [p.y, p.y + (p.h - s.h) / 2, p.y + p.h - s.h]
      const candidates: Rect[] = [
        ...ys.map((y) => ({ x: p.x + p.w + gap, y, ...s })), // right
        ...ys.map((y) => ({ x: p.x - gap - s.w, y, ...s })), // left
        ...xs.map((x) => ({ x, y: p.y + p.h + gap, ...s })), // below
        ...xs.map((x) => ({ x, y: p.y - gap - s.h, ...s })), // above
      ]
      for (const c of candidates) {
        if (placed.some((q) => conflicts(c, q, gap))) continue
        const b = bounds([...placed, c])
        const areaScore = (b.w * b.h) / totalArea
        const aspect = Math.abs(Math.log(b.w / b.h / target))
        const centre = Math.hypot(c.x + c.w / 2, c.y + c.h / 2) / scale
        const overflow =
          (b.w > maxWidth ? (b.w - maxWidth) / maxWidth : 0) +
          (b.h > maxHeight ? (b.h - maxHeight) / maxHeight : 0)
        const score = areaScore + 0.6 * aspect + 0.25 * centre + 6 * overflow + rng() * jitter
        if (!best || score < best.score) best = { rect: c, score }
      }
    }
    // A free spot always exists on the outer boundary, so `best` is set; guard anyway.
    const chosen = best?.rect ?? { x: bounds(placed).x + bounds(placed).w + gap, y: 0, ...s }
    placed.push(chosen)
    rects[idx] = chosen
  }
  return normalize(rects)
}

export const LAYOUTS: Record<LayoutStyle, LayoutFn> = {
  grid: gridLayout,
  row: rowLayout,
  centre: centreLayout,
  salon: salonLayout,
}

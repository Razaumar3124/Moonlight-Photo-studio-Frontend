import { formatLength, type LengthUnit } from '@/lib/units'
import { PLANNER_RULES } from '../constants'
import type { Scene } from './geometry/scene'
import { drawingHeight } from './room'

/**
 * Client-side "Download design": clone the live wall <svg>, inline every image as a data URL
 * (an SVG drawn into a canvas can't load external resources), add the dimension labels as SVG
 * text, rasterise to a high-resolution PNG and trigger a download. No server needed (M11).
 */

const SVG_NS = 'http://www.w3.org/2000/svg'
/** Width of the PNG download; the quote preview is rendered smaller (see `width`). */
const EXPORT_WIDTH_PX = 2400

/**
 * Inline an image as a data URL. Loaded through <img> (CSP `img-src` allows self, the API origin,
 * blob: and data:), NOT fetch(): `connect-src` is kept narrow. Photos come from the API as signed
 * URLs; when the API is on another origin they are requested in CORS mode (the API echoes the
 * allowed frontend origin), otherwise the canvas would be tainted and unreadable. Re-encoding also
 * shrinks uploads to what the output can actually show. WebP keeps transparency; browsers that
 * can't encode it fall back to PNG.
 */
function isCrossOrigin(href: string): boolean {
  if (!/^https?:/i.test(href)) return false
  try {
    return new URL(href).origin !== window.location.origin
  } catch {
    return false
  }
}

async function toDataUrl(
  href: string,
  cache: Map<string, Promise<string>>,
  maxEmbedPx: number,
): Promise<string> {
  const hit = cache.get(href)
  if (hit) return hit
  const task = (async () => {
    const img = new Image()
    if (isCrossOrigin(href)) img.crossOrigin = 'anonymous'
    img.src = href
    await img.decode()
    const scale = Math.min(1, maxEmbedPx / Math.max(img.naturalWidth, img.naturalHeight, 1))
    const canvas = document.createElement('canvas')
    canvas.width = Math.max(1, Math.round(img.naturalWidth * scale))
    canvas.height = Math.max(1, Math.round(img.naturalHeight * scale))
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('Canvas is not available')
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
    return canvas.toDataURL('image/webp', 0.9)
  })()
  cache.set(href, task)
  return task
}

function svgText(
  x: number,
  y: number,
  content: string,
  size: number,
  anchor: 'start' | 'middle' | 'end' = 'middle',
) {
  const t = document.createElementNS(SVG_NS, 'text')
  const attrs: Record<string, string> = {
    x: String(x),
    y: String(y),
    'font-size': String(size),
    'font-family': "'Segoe UI', Helvetica, Arial, sans-serif",
    'font-weight': '600',
    fill: '#2a1712',
    'text-anchor': anchor,
    'paint-order': 'stroke',
    stroke: 'rgba(255,252,247,0.9)',
    'stroke-width': String(size * 0.35),
  }
  Object.entries(attrs).forEach(([k, v]) => t.setAttribute(k, v))
  t.textContent = content
  return t
}

function svgLine(x1: number, y1: number, x2: number, y2: number, width: number, dash?: string) {
  const l = document.createElementNS(SVG_NS, 'line')
  Object.entries({ x1, y1, x2, y2 }).forEach(([k, v]) => l.setAttribute(k, String(v)))
  l.setAttribute('stroke', '#2a1712')
  l.setAttribute('stroke-opacity', '0.55')
  l.setAttribute('stroke-width', String(width))
  if (dash) l.setAttribute('stroke-dasharray', dash)
  return l
}

/** Height label rotated to run along the vertical guide, like an architectural drawing. */
function heightLabel(x: number, y: number, content: string, size: number) {
  const t = svgText(x, y, content, size)
  t.setAttribute('transform', `rotate(-90 ${x} ${y})`)
  return t
}

/** "Living Room Gallery Wall" → "living-room-gallery-wall-moonlight.png" */
export function exportFileName(title: string) {
  const slug = title
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60)
  return `${slug || 'memory-wall'}-moonlight.png`
}

export interface WallImageOptions {
  title: string
  unit: LengthUnit
  guides: boolean
  /** PNG by default; JPEG is what the quote preview uses (small, opaque, works everywhere). */
  format?: 'image/png' | 'image/webp' | 'image/jpeg'
  /** Output width in pixels (default 2400, the PNG download). */
  width?: number
  /** Encoder quality 0–1 for JPEG/WebP. */
  quality?: number
}

/**
 * Render the wall (photos inlined, guides and caption added) to an image Blob. Used by the PNG
 * download and by Request a Quote, so the quote shows exactly what the customer sees.
 */
export async function renderWallImage(
  svg: SVGSVGElement,
  scene: Scene,
  options: WallImageOptions,
): Promise<Blob> {
  const clone = svg.cloneNode(true) as SVGSVGElement
  const outWidth = Math.max(200, Math.round(options.width ?? EXPORT_WIDTH_PX))
  const { w: W, h: H } = scene.wall
  // The drawing is the wall plus the floor band beneath it (see WallSvg / lib/room.ts).
  const VH = drawingHeight(H)

  // Static output: drop interactive-only bits; CSS transforms (used for animation) → attributes.
  clone.querySelectorAll('[data-export="exclude"]').forEach((el) => el.remove())
  clone.querySelectorAll<SVGElement>('[data-tx]').forEach((el) => {
    el.setAttribute('transform', `translate(${el.dataset.tx} ${el.dataset.ty})`)
    el.style.removeProperty('transform')
    el.style.removeProperty('transition')
  })

  // Promises are cached so 9 frames sharing one sample decode it once, not 9 times in parallel.
  const cache = new Map<string, Promise<string>>()
  await Promise.all(
    [...clone.querySelectorAll('image')].map(async (img) => {
      const href = img.getAttribute('href')
      if (href && !href.startsWith('data:')) img.setAttribute('href', await toDataUrl(href, cache, outWidth))
    }),
  )

  if (options.guides) {
    // Label size from the SHORTER side, so very wide or tall walls still get readable, unclipped text.
    const s = Math.min(W, H) / 34
    const g = document.createElementNS(SVG_NS, 'g')
    const yTop = Math.max(H * 0.07, s * 1.5)
    const xLeft = W * 0.045
    const eyeUnit: LengthUnit = options.unit === 'ft' ? 'in' : options.unit
    g.append(
      svgLine(W * 0.1, yTop, W * 0.9, yTop, s * 0.08),
      svgText(W / 2, yTop - s * 0.45, `${formatLength(W, options.unit)} (Wall Width)`, s),
      svgLine(xLeft, H * 0.14, xLeft, H * 0.86, s * 0.08),
      heightLabel(xLeft - s * 0.45, H / 2, `${formatLength(H, options.unit)} (Wall Height)`, s),
      svgLine(0, scene.eyeLevelY, W, scene.eyeLevelY, s * 0.06, `${s * 0.45} ${s * 0.3}`),
      svgText(
        W * 0.98,
        scene.eyeLevelY - s * 0.45,
        `Gallery eye level (${formatLength(PLANNER_RULES.eyeLevelIn, eyeUnit)})`,
        s * 0.85,
        'end',
      ),
    )
    clone.append(g)
  }

  // Bottom-right corner of the floor band, clear of the centred sofa.
  const caption = svgText(
    W * 0.985,
    VH - (VH - H) * 0.3,
    `${options.title} · Moonlight Photo Studio`,
    Math.max(W, H) / 90,
    'end',
  )
  caption.setAttribute('fill', '#4a3329')
  clone.append(caption)

  const height = Math.round((outWidth * VH) / W)
  clone.setAttribute('xmlns', SVG_NS)
  clone.setAttribute('width', String(outWidth))
  clone.setAttribute('height', String(height))

  const svgBlob = new Blob([new XMLSerializer().serializeToString(clone)], {
    type: 'image/svg+xml;charset=utf-8',
  })
  const svgUrl = URL.createObjectURL(svgBlob)
  try {
    const img = new Image()
    img.src = svgUrl
    await img.decode()

    const canvas = document.createElement('canvas')
    canvas.width = outWidth
    canvas.height = height
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('Canvas is not available')
    const type = options.format ?? 'image/png'
    if (type === 'image/jpeg') {
      // JPEG has no transparency: paint white underneath so nothing turns black.
      ctx.fillStyle = '#ffffff'
      ctx.fillRect(0, 0, outWidth, height)
    }
    ctx.drawImage(img, 0, 0, outWidth, height)

    const quality = type === 'image/png' ? undefined : (options.quality ?? 0.9)
    return await new Promise<Blob>((resolve, reject) =>
      canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('Image encoding failed'))), type, quality),
    )
  } finally {
    URL.revokeObjectURL(svgUrl)
  }
}

export async function downloadWallPng(
  svg: SVGSVGElement,
  scene: Scene,
  options: { title: string; unit: LengthUnit; guides: boolean },
): Promise<void> {
  const png = await renderWallImage(svg, scene, { ...options, format: 'image/png' })
  const pngUrl = URL.createObjectURL(png)
  const a = document.createElement('a')
  a.href = pngUrl
  a.download = exportFileName(options.title)
  document.body.append(a)
  a.click()
  a.remove()
  window.setTimeout(() => URL.revokeObjectURL(pngUrl), 10_000)
}

import { MAX_SIDE_PX, MAX_UPLOAD_BYTES, MAX_UPLOAD_MB, MIN_SIDE_PX } from './photos'

/**
 * Photos are stored with a 2 MB limit. Phone and camera photos are usually bigger, so the browser
 * shrinks them first: it keeps the original pixel size for as long as the file can stay under the
 * limit at a good JPEG quality, and only then reduces the pixel size step by step. Photos that are
 * already small enough are uploaded untouched.
 */

/** Largest long side we keep (4096 px is 13.6 in at 300 dpi, plenty for the biggest frames). */
const LONG_SIDE_LADDER = [4096, 3600, 3000, 2500, 2000, 1600] as const
/** Highest quality first; the lowest still prints well at these sizes. */
const QUALITIES = [0.9, 0.82, 0.74] as const
/** Aim a little under the limit so multipart framing and rounding never tip it over. */
export const TARGET_BYTES = MAX_UPLOAD_BYTES - 64 * 1024
/** Mirrors the API's total-pixel guard (`PHOTO_MAX_PIXELS`): such files are always reduced. */
export const MAX_PIXELS = 25_000_000
/** Files bigger than this are not decoded in the browser at all. */
export const MAX_INPUT_BYTES = 40 * 1024 * 1024
/** Refuse to decode absurd images (the browser would run out of memory). */
const MAX_DECODE_PIXELS = 120_000_000

export interface PreparedPhoto {
  file: File
  widthPx: number
  heightPx: number
  /** True when the file was re-encoded or resized to fit the limit. */
  optimized: boolean
  originalBytes: number
}

export type PrepareResult = { ok: true; photo: PreparedPhoto } | { ok: false; error: string }

type Decoded = {
  source: CanvasImageSource
  width: number
  height: number
  close: () => void
}

/** Decode with the camera's rotation (EXIF) applied, so portrait photos aren't saved sideways. */
async function decode(file: File): Promise<Decoded | null> {
  try {
    if (typeof createImageBitmap === 'function') {
      const bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' })
      return { source: bitmap, width: bitmap.width, height: bitmap.height, close: () => bitmap.close() }
    }
  } catch {
    /* fall through to <img> */
  }
  const url = URL.createObjectURL(file)
  try {
    const img = new Image()
    img.src = url
    await img.decode()
    return {
      source: img,
      width: img.naturalWidth,
      height: img.naturalHeight,
      close: () => undefined,
    }
  } catch {
    return null
  } finally {
    URL.revokeObjectURL(url)
  }
}

function encodeJpeg(decoded: Decoded, width: number, height: number, quality: number): Promise<Blob | null> {
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')
  if (!ctx) return Promise.resolve(null)
  // JPEG has no transparency: white underneath, like a print.
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, width, height)
  ctx.imageSmoothingQuality = 'high'
  ctx.drawImage(decoded.source, 0, 0, width, height)
  return new Promise((resolve) => canvas.toBlob((b) => resolve(b), 'image/jpeg', quality))
}

const jpegName = (name: string) => `${name.replace(/\.[^./\\]+$/, '') || 'photo'}.jpg`

/** "4.1 MB" / "820 KB" for messages. */
export function formatBytes(bytes: number): string {
  return bytes >= 1024 * 1024
    ? `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    : `${Math.max(1, Math.round(bytes / 1024))} KB`
}

/**
 * Get a photo ready to upload: untouched when it already fits, otherwise resized/re-encoded to
 * JPEG under the limit. Fails with a message for photos that can't be used at any size.
 */
export async function preparePhotoForUpload(file: File): Promise<PrepareResult> {
  if (file.size > MAX_INPUT_BYTES) {
    return {
      ok: false,
      error: `That photo is over ${formatBytes(MAX_INPUT_BYTES)}, too large to prepare here. Please choose a smaller one.`,
    }
  }
  const decoded = await decode(file)
  if (!decoded) {
    return {
      ok: false,
      error: 'We couldn’t read that image. It may be damaged or in an unsupported format.',
    }
  }
  try {
    const { width, height } = decoded
    if (Math.min(width, height) < MIN_SIDE_PX) {
      return { ok: false, error: `That photo is too small to print well (under ${MIN_SIDE_PX} px).` }
    }
    if (width * height > MAX_DECODE_PIXELS) {
      return { ok: false, error: 'That photo has too many pixels to prepare. Please choose a smaller one.' }
    }

    const fits =
      file.size <= MAX_UPLOAD_BYTES && width * height <= MAX_PIXELS && Math.max(width, height) <= MAX_SIDE_PX
    if (fits) {
      return {
        ok: true,
        photo: { file, widthPx: width, heightPx: height, optimized: false, originalBytes: file.size },
      }
    }

    const longSide = Math.max(width, height)
    // Start at the original size (capped); never enlarge.
    const top = Math.min(longSide, LONG_SIDE_LADDER[0])
    const sizes = [top, ...LONG_SIDE_LADDER.filter((side) => side < top)]

    for (const side of sizes) {
      const scale = side / longSide
      const w = Math.max(1, Math.round(width * scale))
      const h = Math.max(1, Math.round(height * scale))
      if (Math.min(w, h) < MIN_SIDE_PX) continue
      if (w * h > MAX_PIXELS) continue
      for (const quality of QUALITIES) {
        const blob = await encodeJpeg(decoded, w, h, quality)
        if (!blob) {
          return { ok: false, error: 'We couldn’t prepare that photo in this browser. Please try another.' }
        }
        if (blob.size <= TARGET_BYTES) {
          const out = new File([blob], jpegName(file.name), {
            type: 'image/jpeg',
            lastModified: file.lastModified,
          })
          return {
            ok: true,
            photo: { file: out, widthPx: w, heightPx: h, optimized: true, originalBytes: file.size },
          }
        }
      }
    }
    if (longSide > MAX_SIDE_PX) {
      return {
        ok: false,
        error: `That photo is too large (over ${MAX_SIDE_PX} px on a side). Please resize it first.`,
      }
    }
    return {
      ok: false,
      error: `We couldn’t shrink that photo under ${MAX_UPLOAD_MB} MB. Please choose a simpler or smaller photo.`,
    }
  } finally {
    decoded.close()
  }
}

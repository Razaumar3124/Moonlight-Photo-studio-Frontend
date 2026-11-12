import type { PhotoSummary } from '@/types/api'
import { PHOTO_UPLOAD_MIME_TYPES } from '@/types/api'
import { resolveApiUrl } from '@/services/apiClient'
import type { UploadedPhotoRef } from './plannerState'

/** The API's limits (docs/API_CONTRACT.md §5), checked up front so a bad file never leaves the browser. */
export const MAX_UPLOAD_BYTES = 25 * 1024 * 1024
export const MIN_SIDE_PX = 300
export const MAX_SIDE_PX = 8192

/** An uploaded photo as the planner uses it: ids and metadata, plus the current signed URLs. */
export interface LibraryPhoto {
  id: string
  name: string
  widthPx: number
  heightPx: number
  thumbnailUrl: string
  previewUrl: string
  createdAt: string
  /** Epoch ms when the signed URLs stop working. */
  expiresAt: number
}

/** When a signature has less than this left, the library fetches fresh URLs. */
export const URL_REFRESH_MARGIN_MS = 10 * 60 * 1000

/** The signed URLs carry `exp` (epoch seconds). Unknown or garbled counts as "soon". */
export function signedUrlExpiry(url: string, now = Date.now()): number {
  try {
    const exp = Number(new URL(url, 'http://local.invalid').searchParams.get('exp'))
    return Number.isFinite(exp) && exp > 0 ? exp * 1000 : now + URL_REFRESH_MARGIN_MS
  } catch {
    return now + URL_REFRESH_MARGIN_MS
  }
}

export function toLibraryPhoto(photo: PhotoSummary, now = Date.now()): LibraryPhoto {
  return {
    id: photo.id,
    name: photo.original_filename,
    widthPx: photo.width_px,
    heightPx: photo.height_px,
    thumbnailUrl: resolveApiUrl(photo.thumbnail_url) ?? '',
    previewUrl: resolveApiUrl(photo.preview_url) ?? '',
    createdAt: photo.created_at,
    expiresAt: Math.min(signedUrlExpiry(photo.thumbnail_url, now), signedUrlExpiry(photo.preview_url, now)),
  }
}

/** The state reference for a frame that shows this photo. */
export const toPhotoRef = (
  photo: Pick<LibraryPhoto, 'id' | 'name' | 'widthPx' | 'heightPx'>,
): UploadedPhotoRef => ({
  kind: 'upload',
  photoId: photo.id,
  name: photo.name.slice(0, 120),
  widthPx: photo.widthPx,
  heightPx: photo.heightPx,
})

/** Client-side file checks. Returns a message for the user, or undefined when the file is acceptable. */
export function checkPhotoFile(file: File): string | undefined {
  if (!(PHOTO_UPLOAD_MIME_TYPES as readonly string[]).includes(file.type)) {
    return 'Please choose a JPEG, PNG or WebP photo.'
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return 'That photo is larger than 25 MB. Please choose a smaller file.'
  }
  if (file.size === 0) return 'That file is empty.'
  return undefined
}

/** Pixel size of the dimension check (needs decoding, so it's separate from `checkPhotoFile`). */
export function checkPhotoDimensions(widthPx: number, heightPx: number): string | undefined {
  if (Math.min(widthPx, heightPx) < MIN_SIDE_PX) {
    return `That photo is too small to print well (under ${MIN_SIDE_PX} px).`
  }
  if (Math.max(widthPx, heightPx) > MAX_SIDE_PX) {
    return `That photo is too large (over ${MAX_SIDE_PX} px on a side). Please resize it first.`
  }
  return undefined
}

/** Effective print resolution of a photo cropped to fill an opening (cover). */
export function effectiveDpi(widthPx: number, heightPx: number, opening: { w: number; h: number }) {
  return Math.round(Math.min(widthPx / opening.w, heightPx / opening.h))
}

export function dpiQuality(dpi: number): { label: string; tone: 'success' | 'warning' | 'error' } {
  if (dpi >= 300) return { label: 'Excellent print quality', tone: 'success' }
  if (dpi >= 150) return { label: 'Good print quality', tone: 'success' }
  if (dpi >= 100) return { label: 'Fair. May look soft up close', tone: 'warning' }
  return { label: 'Low. Choose a smaller frame or larger photo', tone: 'error' }
}

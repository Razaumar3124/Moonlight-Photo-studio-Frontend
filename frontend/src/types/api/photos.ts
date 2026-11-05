/** Contract §4 — Photo Management. */
import type { EntityId, ISODateTime, PhotoOrientation } from './common'

/** POST /photos/upload (multipart, field `file`; JPEG/PNG/WebP) → 201 */
export interface Photo {
  id: EntityId
  original_filename: string
  mime_type: 'image/jpeg' | 'image/png' | 'image/webp' | (string & {})
  file_size_bytes: number
  width_px: number
  height_px: number
  aspect_ratio: number
  suggested_orientation: PhotoOrientation
  /** Relative API path. If it requires the Bearer token, <img src> cannot load it (Q5). */
  thumbnail_url: string
  preview_url: string
  created_at: ISODateTime
}

/** GET /photos list item — a subset of Photo. */
export type PhotoSummary = Pick<
  Photo,
  'id' | 'original_filename' | 'width_px' | 'height_px' | 'aspect_ratio' | 'thumbnail_url' | 'created_at'
>

export const PHOTO_UPLOAD_MIME_TYPES = ['image/jpeg', 'image/png', 'image/webp'] as const

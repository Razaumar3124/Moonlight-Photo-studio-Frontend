/** Contract §5 — Photo Management. */
import type { EntityId, ISODateTime } from './common'

/** POST /photos/upload (multipart, field `file`; JPEG/PNG/WebP, ≤ 25 MB) → 201 */
export interface Photo {
  id: EntityId
  user_id: EntityId
  original_filename: string
  mime_type: 'image/jpeg' | 'image/png' | 'image/webp' | (string & {})
  file_size_bytes: number
  width_px: number
  height_px: number
  aspect_ratio: number
  suggested_orientation: 'portrait' | 'landscape' | 'square'
  /**
   * Short-lived signed API paths (Q5 resolved): usable directly in `<img src>` without the
   * Bearer header. Resolve against the API origin with `resolveApiUrl`.
   */
  thumbnail_url: string
  preview_url: string
  created_at: ISODateTime
}

/** GET /photos list item — a subset of Photo. */
export type PhotoSummary = Pick<
  Photo,
  | 'id'
  | 'original_filename'
  | 'width_px'
  | 'height_px'
  | 'aspect_ratio'
  | 'thumbnail_url'
  | 'preview_url'
  | 'created_at'
>

/** GET /photos?page&page_size */
export interface PhotosListResponse {
  items: PhotoSummary[]
  total: number
  page: number
  page_size: number
}

export const PHOTO_UPLOAD_MIME_TYPES = ['image/jpeg', 'image/png', 'image/webp'] as const

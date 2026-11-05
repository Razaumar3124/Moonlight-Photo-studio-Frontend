import { useCallback, useEffect, useRef } from 'react'
import { PHOTO_UPLOAD_MIME_TYPES } from '@/types/api'
import type { PhotoRef } from '../lib/plannerState'

export const MAX_UPLOAD_BYTES = 25 * 1024 * 1024
const MIN_SIDE_PX = 300

export type UploadResult =
  { ok: true; photo: Extract<PhotoRef, { kind: 'upload' }> } | { ok: false; error: string }

/**
 * Session-only photo "upload" for the UI phases: validates the file, reads its pixel size and
 * returns an object URL. URLs are kept alive for the whole visit (undo / saved designs may still
 * show them) and revoked when the planner unmounts. Phase 5 replaces this with POST /photos/upload.
 */
export function usePhotoUpload() {
  const urls = useRef(new Set<string>())

  useEffect(() => {
    const set = urls.current
    return () => {
      set.forEach((u) => URL.revokeObjectURL(u))
      set.clear()
    }
  }, [])

  return useCallback(async (file: File): Promise<UploadResult> => {
    if (!(PHOTO_UPLOAD_MIME_TYPES as readonly string[]).includes(file.type)) {
      return { ok: false, error: 'Please choose a JPEG, PNG or WebP photo.' }
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      return { ok: false, error: 'That photo is larger than 25 MB. Please choose a smaller file.' }
    }
    const url = URL.createObjectURL(file)
    try {
      const img = new Image()
      img.src = url
      await img.decode()
      if (Math.min(img.naturalWidth, img.naturalHeight) < MIN_SIDE_PX) {
        URL.revokeObjectURL(url)
        return { ok: false, error: `That photo is too small to print well (under ${MIN_SIDE_PX} px).` }
      }
      urls.current.add(url)
      return {
        ok: true,
        photo: {
          kind: 'upload',
          url,
          name: file.name.slice(0, 120),
          widthPx: img.naturalWidth,
          heightPx: img.naturalHeight,
        },
      }
    } catch {
      URL.revokeObjectURL(url)
      return {
        ok: false,
        error: 'We couldn’t read that image. It may be damaged or in an unsupported format.',
      }
    }
  }, [])
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

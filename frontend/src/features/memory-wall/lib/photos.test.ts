import { describe, expect, it } from 'vitest'
import {
  checkPhotoFile,
  MAX_UPLOAD_BYTES,
  MAX_UPLOAD_MB,
  PHOTO_TOO_LARGE_MESSAGE,
  PHOTO_UPLOAD_HINT,
  PHOTO_UPLOAD_HINT_LONG,
} from './photos'

describe('the 2 MB photo rule shown to customers', () => {
  it('is 2 MB everywhere', () => {
    expect(MAX_UPLOAD_MB).toBe(2)
    expect(MAX_UPLOAD_BYTES).toBe(2 * 1024 * 1024)
    expect(PHOTO_UPLOAD_HINT).toBe('JPEG, PNG or WebP · up to 2 MB')
    expect(PHOTO_UPLOAD_HINT_LONG).toMatch(/up to 2 MB.*shrunk automatically/)
    expect(PHOTO_TOO_LARGE_MESSAGE).toMatch(/larger than 2 MB/)
    expect(`${PHOTO_UPLOAD_HINT_LONG}${PHOTO_TOO_LARGE_MESSAGE}`).not.toMatch(/25 MB/)
  })

  it('checkPhotoFile checks type and emptiness; size is handled by the shrinking step', () => {
    const f = (type: string, size: number) => new File([new Uint8Array(size)], 'a', { type })
    expect(checkPhotoFile(f('image/gif', 10))).toMatch(/JPEG, PNG or WebP/)
    expect(checkPhotoFile(f('image/jpeg', 0))).toMatch(/empty/)
    expect(checkPhotoFile(f('image/jpeg', 6 * 1024 * 1024))).toBeUndefined()
  })
})

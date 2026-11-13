// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectiveDpi } from './photos'
import {
  formatBytes,
  MAX_INPUT_BYTES,
  MAX_PIXELS,
  preparePhotoForUpload,
  TARGET_BYTES,
} from './photoCompress'

const MB = 1024 * 1024
const file = (name: string, size: number, type = 'image/jpeg') =>
  new File([new Uint8Array(size)], name, { type, lastModified: 7 })

interface Canvases {
  encodes: { w: number; h: number; q: number }[]
}

/** Decoded size of the next photo, and how many bytes the fake encoder produces. */
function stubBrowser(
  dims: { w: number; h: number },
  bytes: (w: number, h: number, q: number) => number = () => 500_000,
): Canvases {
  const seen: Canvases = { encodes: [] }
  const bitmap = { width: dims.w, height: dims.h, close: vi.fn<() => void>() }
  vi.stubGlobal('createImageBitmap', vi.fn<() => Promise<unknown>>().mockResolvedValue(bitmap))
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
    fillRect: () => undefined,
    drawImage: () => undefined,
  } as unknown as CanvasRenderingContext2D)
  vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation(function (
    this: HTMLCanvasElement,
    cb: BlobCallback,
    type?: string,
    quality?: number,
  ) {
    seen.encodes.push({ w: this.width, h: this.height, q: quality ?? 0 })
    cb(new Blob([new Uint8Array(bytes(this.width, this.height, quality ?? 0))], { type }))
  })
  return seen
}

beforeEach(() => {
  URL.createObjectURL = () => 'blob:test'
  URL.revokeObjectURL = () => undefined
})
afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('preparePhotoForUpload: photos that already fit', () => {
  it('uploads a photo under 2 MB untouched, whatever its format', async () => {
    const encodes = stubBrowser({ w: 3000, h: 2000 })
    for (const [name, type] of [
      ['a.jpg', 'image/jpeg'],
      ['b.png', 'image/png'],
      ['c.webp', 'image/webp'],
    ] as const) {
      const original = file(name, 1.5 * MB, type)
      const result = await preparePhotoForUpload(original)
      expect(result).toMatchObject({ ok: true, photo: { optimized: false, widthPx: 3000, heightPx: 2000 } })
      expect(result.ok && result.photo.file === original).toBe(true)
    }
    expect(encodes.encodes).toHaveLength(0)
  })

  it('accepts exactly 2 MB but not a byte more', async () => {
    const encodes = stubBrowser({ w: 3000, h: 2000 })
    const exact = await preparePhotoForUpload(file('a.jpg', 2 * MB))
    expect(exact).toMatchObject({ ok: true, photo: { optimized: false } })
    const over = await preparePhotoForUpload(file('b.jpg', 2 * MB + 1))
    expect(over).toMatchObject({ ok: true, photo: { optimized: true } })
    expect(encodes.encodes.length).toBeGreaterThan(0)
  })

  it('closes the decoded bitmap', async () => {
    stubBrowser({ w: 3000, h: 2000 })
    await preparePhotoForUpload(file('a.jpg', 1000))
    const bitmap = await (createImageBitmap as unknown as () => Promise<{ close: () => void }>)()
    expect(bitmap.close).toHaveBeenCalledTimes(1)
  })
})

describe('preparePhotoForUpload: shrinking', () => {
  it('re-encodes a large photo as JPEG under the limit and keeps the original pixel size when it can', async () => {
    const seen = stubBrowser({ w: 4000, h: 3000 }, () => 1_200_000)
    const result = await preparePhotoForUpload(file('Holiday Photo.PNG', 6 * MB, 'image/png'))
    expect(result).toMatchObject({
      ok: true,
      photo: { optimized: true, widthPx: 4000, heightPx: 3000, originalBytes: 6 * MB },
    })
    if (!result.ok) return
    expect(result.photo.file.type).toBe('image/jpeg')
    expect(result.photo.file.name).toBe('Holiday Photo.jpg')
    expect(result.photo.file.size).toBeLessThanOrEqual(TARGET_BYTES)
    expect(seen.encodes).toEqual([{ w: 4000, h: 3000, q: 0.9 }]) // first try at full size
  })

  it('lowers quality before it lowers the pixel size', async () => {
    const seen = stubBrowser({ w: 4000, h: 3000 }, (_w, _h, q) =>
      q >= 0.9 ? 3 * MB : q >= 0.82 ? 2.5 * MB : 1.5 * MB,
    )
    const result = await preparePhotoForUpload(file('a.jpg', 8 * MB))
    expect(result).toMatchObject({ ok: true, photo: { widthPx: 4000, heightPx: 3000 } })
    expect(seen.encodes.map((e) => e.q)).toEqual([0.9, 0.82, 0.74])
    expect(new Set(seen.encodes.map((e) => e.w))).toEqual(new Set([4000]))
  })

  it('reduces the pixel size step by step when quality alone is not enough', async () => {
    const seen = stubBrowser({ w: 4000, h: 3000 }, (w) => (w > 3000 ? 5 * MB : 1.2 * MB))
    const result = await preparePhotoForUpload(file('a.jpg', 9 * MB))
    expect(result).toMatchObject({ ok: true })
    if (!result.ok) return
    expect(result.photo.widthPx).toBeLessThanOrEqual(3000)
    expect(result.photo.widthPx / result.photo.heightPx).toBeCloseTo(4 / 3, 2)
    expect(seen.encodes.at(-1)?.w).toBe(result.photo.widthPx)
  })

  it('never enlarges a photo', async () => {
    const seen = stubBrowser({ w: 1800, h: 1200 }, () => 1 * MB)
    const result = await preparePhotoForUpload(file('a.png', 3 * MB, 'image/png'))
    expect(result).toMatchObject({ ok: true, photo: { widthPx: 1800, heightPx: 1200 } })
    expect(Math.max(...seen.encodes.map((e) => e.w))).toBe(1800)
  })

  it('caps very large photos at 4096 px on the long side', async () => {
    stubBrowser({ w: 8000, h: 6000 }, () => 1 * MB)
    const result = await preparePhotoForUpload(file('a.jpg', 9 * MB))
    expect(result).toMatchObject({ ok: true, photo: { widthPx: 4096, heightPx: 3072 } })
  })

  it('always reduces photos over the pixel cap, even if the file is small', async () => {
    stubBrowser({ w: 6000, h: 5000 }, () => 400_000) // 30 MP, tiny file
    expect(6000 * 5000).toBeGreaterThan(MAX_PIXELS)
    const result = await preparePhotoForUpload(file('flat.jpg', 300_000))
    expect(result).toMatchObject({ ok: true, photo: { optimized: true } })
    expect(result.ok && result.photo.widthPx * result.photo.heightPx <= MAX_PIXELS).toBe(true)
  })

  it('reduces panoramas wider than the API allows', async () => {
    stubBrowser({ w: 9000, h: 3000 }, () => 800_000)
    const result = await preparePhotoForUpload(file('pano.jpg', 1 * MB))
    expect(result).toMatchObject({ ok: true, photo: { optimized: true, widthPx: 4096 } })
  })

  it('gives up with a clear message when nothing fits', async () => {
    stubBrowser({ w: 4000, h: 3000 }, () => 5 * MB)
    const result = await preparePhotoForUpload(file('noise.jpg', 20 * MB))
    expect(result).toEqual({
      ok: false,
      error: expect.stringMatching(/couldn’t shrink that photo under 2 MB/),
    })
  })

  it('reports an encoder that is not available', async () => {
    stubBrowser({ w: 4000, h: 3000 })
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null)
    const result = await preparePhotoForUpload(file('a.jpg', 5 * MB))
    expect(result).toMatchObject({ ok: false, error: expect.stringMatching(/in this browser/) })
  })
})

describe('preparePhotoForUpload: photos that cannot be used', () => {
  it('rejects photos too small to print before doing any work', async () => {
    const seen = stubBrowser({ w: 200, h: 5000 })
    const result = await preparePhotoForUpload(file('thin.jpg', 5 * MB))
    expect(result).toEqual({ ok: false, error: expect.stringMatching(/too small to print/) })
    expect(seen.encodes).toHaveLength(0)
  })

  it('does not even decode files over the browser input cap', async () => {
    stubBrowser({ w: 3000, h: 2000 })
    const result = await preparePhotoForUpload(file('huge.jpg', MAX_INPUT_BYTES + 1))
    expect(result).toEqual({ ok: false, error: expect.stringMatching(/too large to prepare/) })
    expect(createImageBitmap).not.toHaveBeenCalled()
  })

  it('refuses absurd pixel counts instead of risking the browser', async () => {
    stubBrowser({ w: 20000, h: 10000 })
    const result = await preparePhotoForUpload(file('gigapixel.jpg', 30 * MB))
    expect(result).toEqual({ ok: false, error: expect.stringMatching(/too many pixels/) })
  })

  it('reports files that cannot be decoded', async () => {
    vi.stubGlobal('createImageBitmap', vi.fn<() => Promise<unknown>>().mockRejectedValue(new Error('bad')))
    vi.stubGlobal(
      'Image',
      class {
        set src(_v: string) {}
        decode() {
          return Promise.reject(new Error('bad'))
        }
      },
    )
    const result = await preparePhotoForUpload(file('broken.jpg', 3 * MB))
    expect(result).toEqual({ ok: false, error: expect.stringMatching(/couldn’t read that image/) })
  })

  it('falls back to <img> decoding when createImageBitmap is unavailable', async () => {
    vi.stubGlobal('createImageBitmap', undefined)
    vi.stubGlobal(
      'Image',
      class {
        naturalWidth = 3000
        naturalHeight = 2000
        set src(_v: string) {}
        decode() {
          return Promise.resolve()
        }
      },
    )
    const result = await preparePhotoForUpload(file('a.jpg', 1000))
    expect(result).toMatchObject({ ok: true, photo: { widthPx: 3000, heightPx: 2000 } })
  })
})

describe('print-quality warnings still work after shrinking', () => {
  it('reports the real pixel size, so the DPI label reflects what was stored', async () => {
    stubBrowser({ w: 6000, h: 4000 }, () => 1 * MB)
    const result = await preparePhotoForUpload(file('big.jpg', 9 * MB))
    expect(result.ok).toBe(true)
    if (!result.ok) return
    // 4096 x 2731 px on a 24 x 36 in opening is low resolution and must say so.
    const dpi = effectiveDpi(result.photo.widthPx, result.photo.heightPx, { w: 36, h: 24 })
    expect(dpi).toBeLessThan(150)
    // ...while the same file on a 12 x 16 in frame stays good.
    expect(
      effectiveDpi(result.photo.widthPx, result.photo.heightPx, { w: 16, h: 12 }),
    ).toBeGreaterThanOrEqual(200)
  })
})

describe('formatBytes', () => {
  it.each([
    [5 * MB, '5.0 MB'],
    [4.1 * MB, '4.1 MB'],
    [820 * 1024, '820 KB'],
    [10, '1 KB'],
  ])('%d -> %s', (bytes, text) => expect(formatBytes(bytes)).toBe(text))
})

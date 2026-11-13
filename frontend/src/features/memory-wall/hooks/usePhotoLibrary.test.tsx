// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import { StrictMode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/services/apiClient'
import { photosService } from '@/services/photosService'
import type { Photo, PhotoSummary } from '@/types/api'
import { usePhotoLibrary } from './usePhotoLibrary'

vi.mock('@/services/photosService', () => ({
  photosService: {
    listAll: vi.fn<() => Promise<unknown>>(),
    upload: vi.fn<() => Promise<unknown>>(),
    remove: vi.fn<() => Promise<unknown>>(),
  },
}))

const svc = vi.mocked(photosService)
const NOW = 1_800_000_000_000
const exp = (ms: number) => Math.floor(ms / 1000)

const summary = (id: string, expiresInMs = 24 * 3600 * 1000): PhotoSummary => ({
  id,
  original_filename: `${id}.jpg`,
  width_px: 3000,
  height_px: 2000,
  aspect_ratio: 1.5,
  thumbnail_url: `/api/v1/photos/${id}/thumbnail?sig=t&exp=${exp(Date.now() + expiresInMs)}`,
  preview_url: `/api/v1/photos/${id}/preview?sig=p&exp=${exp(Date.now() + expiresInMs)}`,
  created_at: '2026-11-12T00:00:00Z',
})
const uploaded = (id: string): Photo => ({
  ...summary(id),
  user_id: 'u',
  mime_type: 'image/jpeg',
  file_size_bytes: 1000,
  suggested_orientation: 'landscape',
})
const A = '665f1c2e9b1d4a0000000001'
const B = '665f1c2e9b1d4a0000000002'

let dims = { w: 3000, h: 2000 }
beforeEach(() => {
  vi.resetAllMocks()
  dims = { w: 3000, h: 2000 }
  vi.stubGlobal(
    'Image',
    class {
      naturalWidth = dims.w
      naturalHeight = dims.h
      set src(_value: string) {}
      decode() {
        return Promise.resolve()
      }
    },
  )
  URL.createObjectURL = () => 'blob:test'
  URL.revokeObjectURL = () => undefined
})
afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

const file = (name = 'a.jpg', type = 'image/jpeg', size = 1000, lastModified = 1) =>
  new File([new Uint8Array(size)], name, { type, lastModified })

async function ready(photos: PhotoSummary[] = []) {
  svc.listAll.mockResolvedValue(photos)
  const hook = renderHook(() => usePhotoLibrary())
  await waitFor(() => expect(hook.result.current.status).toBe('ready'))
  return hook
}

describe('loading', () => {
  it('lists the library and resolves each photo to its signed preview URL', async () => {
    const { result } = await ready([summary(A)])
    expect(result.current.photos.map((p) => p.id)).toEqual([A])
    expect(result.current.urlFor(A)).toContain(`/photos/${A}/preview?sig=p`)
    expect(result.current.photos[0]?.thumbnailUrl).toContain('/thumbnail?')
    expect(result.current.urlFor('missing')).toBeUndefined()
    expect(result.current.has(A)).toBe(true)
  })

  it('reports a failed first load as an error that "refresh" can recover from', async () => {
    svc.listAll.mockRejectedValueOnce(new ApiError({ status: 0, code: 'NETWORK_ERROR', message: 'x' }))
    const { result } = renderHook(() => usePhotoLibrary())
    await waitFor(() => expect(result.current.status).toBe('error'))
    svc.listAll.mockResolvedValue([summary(A)])
    await act(() => result.current.refresh())
    expect(result.current.status).toBe('ready')
    expect(result.current.photos).toHaveLength(1)
  })

  it('keeps the photos it has when a later refresh fails', async () => {
    const { result } = await ready([summary(A)])
    svc.listAll.mockRejectedValue(new Error('down'))
    await act(() => result.current.refresh())
    expect(result.current.status).toBe('ready')
    expect(result.current.photos).toHaveLength(1)
  })
})

describe('React StrictMode (dev double effects)', () => {
  it('still loads the library when the first request is aborted by the effect cleanup', async () => {
    // Like the real client: a request whose signal is aborted rejects with AbortError.
    svc.listAll.mockImplementation(
      (signal?: unknown) =>
        new Promise((resolve, reject) => {
          const s = signal as AbortSignal
          s.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
          setTimeout(() => resolve([summary(A)]), 5)
        }),
    )
    const { result } = renderHook(() => usePhotoLibrary(), { wrapper: StrictMode })
    await waitFor(() => expect(result.current.status).toBe('ready'))
    expect(result.current.photos.map((p) => p.id)).toEqual([A])
  })
})

describe('signed URLs', () => {
  it('refreshes before the signature expires (periodic check)', async () => {
    vi.useFakeTimers({ now: NOW, shouldAdvanceTime: false })
    svc.listAll.mockResolvedValueOnce([summary(A, 5 * 60 * 1000)])
    const { result } = renderHook(() => usePhotoLibrary())
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(result.current.status).toBe('ready')
    const first = result.current.urlFor(A)
    svc.listAll.mockResolvedValue([{ ...summary(A, 24 * 3600 * 1000) }])
    await act(async () => {
      await vi.advanceTimersByTimeAsync(61_000)
    })
    expect(svc.listAll).toHaveBeenCalledTimes(2)
    expect(result.current.urlFor(A)).not.toBe(first)
  })

  it('does not refresh while the signatures are comfortably valid', async () => {
    vi.useFakeTimers({ now: NOW })
    svc.listAll.mockResolvedValue([summary(A)])
    renderHook(() => usePhotoLibrary())
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5 * 60 * 1000)
    })
    expect(svc.listAll).toHaveBeenCalledTimes(1)
  })

  it('refreshes when a broken image is reported, at most once in a short while', async () => {
    vi.useFakeTimers({ now: NOW })
    svc.listAll.mockResolvedValue([summary(A)])
    const { result } = renderHook(() => usePhotoLibrary())
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0)
    })
    await act(async () => {
      result.current.reportBroken()
      result.current.reportBroken()
      result.current.reportBroken()
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(svc.listAll).toHaveBeenCalledTimes(2)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(20_000)
      result.current.reportBroken()
      await vi.advanceTimersByTimeAsync(0)
    })
    expect(svc.listAll).toHaveBeenCalledTimes(3)
  })
})

describe('upload', () => {
  it('validates the file before sending anything', async () => {
    const { result } = await ready()
    expect(await result.current.upload(file('a.gif', 'image/gif'))).toEqual({
      ok: false,
      error: 'Please choose a JPEG, PNG or WebP photo.',
    })
    expect(await result.current.upload(file('big.jpg', 'image/jpeg', 41 * 1024 * 1024))).toMatchObject({
      ok: false,
      error: expect.stringMatching(/too large to prepare/),
    })
    dims = { w: 200, h: 5000 }
    expect(await result.current.upload(file('thin.jpg'))).toMatchObject({
      ok: false,
      error: expect.stringMatching(/too small/),
    })
    expect(svc.upload).not.toHaveBeenCalled()
  })

  it('sends a photo under 2 MB as it is, with no notice', async () => {
    const { result } = await ready()
    svc.upload.mockResolvedValue(uploaded(A))
    const small = file('small.jpg', 'image/jpeg', 1.5 * 1024 * 1024)
    const outcome = await result.current.upload(small)
    expect(outcome).toMatchObject({ ok: true })
    expect(outcome.ok && outcome.notice).toBeFalsy()
    expect(svc.upload.mock.calls[0]?.[0]).toBe(small)
  })

  it('shrinks a photo over 2 MB before upload and tells the customer', async () => {
    const { result } = await ready()
    svc.upload.mockResolvedValue(uploaded(A))
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
      fillRect: () => undefined,
      drawImage: () => undefined,
    } as unknown as CanvasRenderingContext2D)
    vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation((cb, type) =>
      cb(new Blob([new Uint8Array(1_000_000)], { type })),
    )
    const big = file('IMG_0001.HEIC.jpg', 'image/jpeg', 5 * 1024 * 1024)
    const outcome = await result.current.upload(big)
    expect(outcome).toMatchObject({ ok: true, notice: expect.stringMatching(/5\.0 MB.*optimised.*977 KB/) })
    const sent = svc.upload.mock.calls[0]?.[0] as File
    expect(sent).not.toBe(big)
    expect(sent.size).toBeLessThanOrEqual(2 * 1024 * 1024)
    expect(sent.type).toBe('image/jpeg')
    vi.restoreAllMocks()
  })

  it('uploads, reports progress, adds the photo to the library and returns the frame reference', async () => {
    const { result } = await ready()
    svc.upload.mockImplementation(async (_f, options) => {
      options?.onProgress?.(0.5)
      return uploaded(A)
    })
    const progress: number[] = []
    let outcome: Awaited<ReturnType<typeof result.current.upload>> | undefined
    await act(async () => {
      outcome = await result.current.upload(file(), { onProgress: (p) => progress.push(p) })
    })
    expect(progress).toEqual([0.5])
    expect(outcome).toMatchObject({
      ok: true,
      reused: false,
      photo: { kind: 'upload', photoId: A, widthPx: 3000 },
    })
    expect(result.current.has(A)).toBe(true)
  })

  it('does not upload the same file twice: reuses it while it is in the library', async () => {
    const { result } = await ready()
    svc.upload.mockResolvedValue(uploaded(A))
    await act(async () => {
      await result.current.upload(file('same.jpg', 'image/jpeg', 1000, 7))
    })
    let second: Awaited<ReturnType<typeof result.current.upload>> | undefined
    await act(async () => {
      second = await result.current.upload(file('same.jpg', 'image/jpeg', 1000, 7))
    })
    expect(svc.upload).toHaveBeenCalledTimes(1)
    expect(second).toMatchObject({ ok: true, reused: true })
  })

  it('collapses a double click into one request', async () => {
    const { result } = await ready()
    let release: (p: Photo) => void = () => undefined
    svc.upload.mockReturnValue(new Promise((resolve) => (release = resolve)))
    let both: Awaited<ReturnType<typeof result.current.upload>>[] = []
    await act(async () => {
      const f = file('dbl.jpg', 'image/jpeg', 1000, 9)
      const pending = Promise.all([result.current.upload(f), result.current.upload(f)])
      await Promise.resolve()
      release(uploaded(A))
      both = await pending
    })
    expect(svc.upload).toHaveBeenCalledTimes(1)
    expect(both.every((r) => r.ok)).toBe(true)
  })

  it('uploads again after the photo was deleted', async () => {
    const { result } = await ready()
    svc.upload.mockResolvedValueOnce(uploaded(A)).mockResolvedValueOnce(uploaded(B))
    svc.remove.mockResolvedValue(undefined)
    await act(async () => {
      await result.current.upload(file('x.jpg', 'image/jpeg', 1000, 3))
      await result.current.remove(A)
      await result.current.upload(file('x.jpg', 'image/jpeg', 1000, 3))
    })
    expect(svc.upload).toHaveBeenCalledTimes(2)
  })

  it.each([
    [new ApiError({ status: 0, code: 'NETWORK_ERROR', message: 'x' }), /offline/],
    [new ApiError({ status: 429, code: 'RATE_LIMIT_EXCEEDED', message: 'x' }), /wait a little/],
    [new ApiError({ status: 413, code: 'PAYLOAD_TOO_LARGE', message: 'x' }), /larger than 2 MB/],
    [new ApiError({ status: 503, code: 'STORAGE_LIMIT_REACHED', message: 'x' }), /storage is full/],
    [
      new ApiError({
        status: 422,
        code: 'VALIDATION_ERROR',
        message: 'x',
        details: [{ field: 'file', issue: 'Image is smaller than 300 px' }],
      }),
      /Image is smaller than 300 px/,
    ],
    [new ApiError({ status: 503, code: 'STORAGE_UNAVAILABLE', message: 'x' }), /unavailable/],
    [new ApiError({ status: 500, code: 'INTERNAL_ERROR', message: 'Traceback…' }), /couldn’t upload/],
  ])(
    'maps a failed upload (%#) to a safe message, and a retry of the same file is allowed',
    async (error, message) => {
      const { result } = await ready()
      svc.upload.mockRejectedValueOnce(error)
      const f = file('retry.jpg', 'image/jpeg', 1000, 11)
      let first: Awaited<ReturnType<typeof result.current.upload>> | undefined
      await act(async () => {
        first = await result.current.upload(f)
      })
      expect(first).toMatchObject({ ok: false, error: expect.stringMatching(message) })
      expect(JSON.stringify(first)).not.toMatch(/Traceback/)
      svc.upload.mockResolvedValueOnce(uploaded(A))
      await act(async () => {
        first = await result.current.upload(f)
      })
      expect(first).toMatchObject({ ok: true })
      expect(svc.upload).toHaveBeenCalledTimes(2)
    },
  )
})

describe('remove', () => {
  it('removes a photo from the library', async () => {
    const { result } = await ready([summary(A), summary(B)])
    svc.remove.mockResolvedValue(undefined)
    await act(async () => {
      expect(await result.current.remove(A)).toEqual({ ok: true })
    })
    expect(result.current.photos.map((p) => p.id)).toEqual([B])
  })

  it('keeps the photo and explains when a saved design still uses it', async () => {
    const { result } = await ready([summary(A)])
    svc.remove.mockRejectedValue(
      new ApiError({
        status: 409,
        code: 'PHOTO_IN_USE',
        message: 'This photo is used in 2 saved designs. Remove it from those designs before deleting it.',
      }),
    )
    let outcome: Awaited<ReturnType<typeof result.current.remove>> | undefined
    await act(async () => {
      outcome = await result.current.remove(A)
    })
    expect(outcome).toMatchObject({ ok: false, inUse: true, error: expect.stringMatching(/2 saved designs/) })
    expect(result.current.has(A)).toBe(true)
  })

  it('treats an already-deleted photo as deleted, and reports other failures without dropping it', async () => {
    const { result } = await ready([summary(A), summary(B)])
    svc.remove.mockRejectedValueOnce(new ApiError({ status: 404, code: 'RESOURCE_NOT_FOUND', message: 'x' }))
    await act(async () => {
      expect(await result.current.remove(A)).toEqual({ ok: true })
    })
    svc.remove.mockRejectedValueOnce(new ApiError({ status: 0, code: 'NETWORK_ERROR', message: 'x' }))
    await act(async () => {
      expect(await result.current.remove(B)).toMatchObject({
        ok: false,
        inUse: false,
        error: expect.stringMatching(/offline/),
      })
    })
    expect(result.current.has(B)).toBe(true)
  })
})

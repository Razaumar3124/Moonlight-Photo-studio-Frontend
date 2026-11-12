import { afterEach, describe, expect, it, vi } from 'vitest'
import { quotesService } from './quotesService'

afterEach(() => vi.unstubAllGlobals())

describe('quotesService.prepare', () => {
  it('posts multipart design_data + file with the idempotency key, CSRF header and credentials', async () => {
    const fetchMock = vi.fn<typeof fetch>(
      async () =>
        new Response(JSON.stringify({ quote_id: 'MQ-1' }), {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
        }),
    )
    vi.stubGlobal('fetch', fetchMock)
    const blob = new Blob(['x'], { type: 'image/webp' })

    await quotesService.prepare({ wall: { widthIn: 144, heightIn: 108 }, frames: [] }, blob, 'key-0123456789')

    const [url, init] = fetchMock.mock.calls[0] ?? []
    expect(String(url)).toBe('/api/v1/quotes/prepare')
    expect(init?.method).toBe('POST')
    expect(init?.credentials).toBe('include')
    const headers = new Headers(init?.headers)
    expect(headers.get('Idempotency-Key')).toBe('key-0123456789')
    expect(headers.get('X-CSRF-Protection')).toBe('1')
    // The browser sets the multipart boundary itself.
    expect(headers.has('Content-Type')).toBe(false)
    const form = init?.body as FormData
    expect(JSON.parse(String(form.get('design_data')))).toMatchObject({ wall: { widthIn: 144 } })
    const file = form.get('file') as File
    expect(file.name).toBe('wall-preview.webp')
    expect(file.type).toBe('image/webp')
  })
})

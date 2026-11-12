import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createFakeStorage } from '@/test/fakeStorage'

type FetchMock = ReturnType<typeof vi.fn<typeof fetch>>

async function setup(session?: { accessToken: string; expiresAt: number }) {
  vi.stubGlobal('localStorage', createFakeStorage())
  const fetchMock: FetchMock = vi.fn<typeof fetch>()
  vi.stubGlobal('fetch', fetchMock)
  vi.resetModules()
  const client = await import('./apiClient')
  const { tokenStorage } = await import('./tokenStorage') // same fresh instance apiClient uses
  if (session) {
    tokenStorage.save({
      access_token: session.accessToken,
      token_type: 'bearer',
      expires_in: (session.expiresAt - Date.now()) / 1000,
    })
  }
  return { ...client, fetchMock, tokenStorage }
}

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

function lastRequest(fetchMock: FetchMock) {
  const [url, init] = fetchMock.mock.calls.at(-1) ?? []
  return { url: String(url), init: init ?? {}, headers: new Headers(init?.headers) }
}

describe('apiRequest', () => {
  beforeEach(() => vi.useRealTimers())

  it('prefixes /api/v1, serialises query params and JSON bodies', async () => {
    const { api, fetchMock } = await setup()
    fetchMock.mockResolvedValueOnce(json(200, { ok: true }))
    await api.post(
      '/templates',
      { a: 1 },
      { query: { category: 'grid', min: 2, skip: undefined, tags: ['x', 'y'] } },
    )
    const { url, init, headers } = lastRequest(fetchMock)
    expect(url).toBe('/api/v1/templates?category=grid&min=2&tags=x&tags=y')
    expect(init.method).toBe('POST')
    expect(init.body).toBe('{"a":1}')
    expect(headers.get('Content-Type')).toBe('application/json')
    expect(headers.get('Accept')).toBe('application/json')
  })

  it('keeps caller headers given as a Headers instance', async () => {
    const { api, fetchMock } = await setup()
    fetchMock.mockResolvedValueOnce(json(200, {}))
    await api.get('/x', { headers: new Headers({ 'X-Trace': 'abc' }) })
    expect(lastRequest(fetchMock).headers.get('X-Trace')).toBe('abc')
  })

  it('attaches a valid bearer token, and none when expired or opted out', async () => {
    const { api, fetchMock } = await setup({ accessToken: 'tok', expiresAt: Date.now() + 60_000 })
    fetchMock.mockImplementation(async () => json(200, {}))
    await api.get('/me')
    expect(lastRequest(fetchMock).headers.get('Authorization')).toBe('Bearer tok')
    await api.get('/public', { auth: false })
    expect(lastRequest(fetchMock).headers.has('Authorization')).toBe(false)

    const expired = await setup({ accessToken: 'old', expiresAt: Date.now() - 1 })
    expired.fetchMock.mockImplementation(async () => json(200, {}))
    await expired.api.get('/me')
    expect(lastRequest(expired.fetchMock).headers.has('Authorization')).toBe(false)
  })

  it('lets the browser set the multipart boundary for uploads', async () => {
    const { api, fetchMock } = await setup()
    fetchMock.mockResolvedValueOnce(json(201, { id: 1 }))
    await api.upload('/photos/upload', { file: new Blob(['x'], { type: 'image/png' }) })
    const { init, headers } = lastRequest(fetchMock)
    expect(init.body).toBeInstanceOf(FormData)
    expect(headers.has('Content-Type')).toBe(false)
  })

  it('sends the CSRF header on state-changing requests only, and always includes credentials', async () => {
    const { api, fetchMock, CSRF_HEADER } = await setup()
    fetchMock.mockImplementation(async () => json(200, {}))
    await api.post('/auth/refresh')
    expect(lastRequest(fetchMock).headers.get(CSRF_HEADER)).toBe('1')
    expect(lastRequest(fetchMock).init.credentials).toBe('include')
    await api.get('/templates')
    expect(lastRequest(fetchMock).headers.has(CSRF_HEADER)).toBe(false)
    await api.upload('/photos/upload', { file: new Blob(['x']) })
    expect(lastRequest(fetchMock).headers.get(CSRF_HEADER)).toBe('1')
  })

  it('returns undefined for 204', async () => {
    const { api, fetchMock } = await setup()
    fetchMock.mockResolvedValueOnce(new Response(null, { status: 204 }))
    await expect(api.delete('/designs/1')).resolves.toBeUndefined()
  })

  it('parses the contract error envelope', async () => {
    const { api, fetchMock, isApiError } = await setup()
    fetchMock.mockResolvedValueOnce(
      json(422, {
        error: {
          code: 'GEOMETRY_COLLISION_DETECTED',
          message: 'Frames overlap',
          details: [{ field: 'frames', issue: 'overlap' }],
          timestamp: '2026-11-01T22:45:00.000Z',
        },
      }),
    )
    const error = await api.post('/geometry/validate-layout', {}).catch((e: unknown) => e)
    expect(isApiError(error)).toBe(true)
    if (!isApiError(error)) return
    expect(error).toMatchObject({
      status: 422,
      code: 'GEOMETRY_COLLISION_DETECTED',
      message: 'Frames overlap',
    })
    expect(error.fieldErrors).toEqual({ frames: 'overlap' })
    expect(error.isValidationError).toBe(true)
  })

  it('falls back to FastAPI {detail} validation errors', async () => {
    const { api, fetchMock } = await setup()
    fetchMock.mockResolvedValueOnce(json(422, { detail: [{ loc: ['body', 'email'], msg: 'Invalid email' }] }))
    await expect(api.post('/auth/login', {})).rejects.toMatchObject({
      code: 'VALIDATION_ERROR',
      fieldErrors: { email: 'Invalid email' },
    })
  })

  it('does not leak server HTML/text from 5xx pages', async () => {
    const { api, fetchMock } = await setup()
    fetchMock.mockResolvedValueOnce(
      new Response('<html>Traceback (most recent call last)…</html>', { status: 502 }),
    )
    const error = await api.get('/x').catch((e: unknown) => e)
    expect(error).toMatchObject({ status: 502, code: 'INTERNAL_ERROR' })
    expect((error as Error).message).not.toMatch(/Traceback/)
  })

  it('maps network failures to NETWORK_ERROR and lets aborts through untouched', async () => {
    const { api, fetchMock } = await setup()
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    await expect(api.get('/x')).rejects.toMatchObject({ status: 0, code: 'NETWORK_ERROR' })

    fetchMock.mockRejectedValueOnce(new DOMException('Aborted', 'AbortError'))
    await expect(api.get('/x')).rejects.toMatchObject({ name: 'AbortError' })
  })

  it('on 401 with a session: clears tokens and calls the unauthorized handler once', async () => {
    const { api, fetchMock, setUnauthorizedHandler, tokenStorage } = await setup({
      accessToken: 'tok',
      expiresAt: Date.now() + 60_000,
    })
    const handler = vi.fn<(error: unknown) => void>()
    setUnauthorizedHandler(handler)
    fetchMock.mockResolvedValueOnce(
      json(401, { error: { code: 'TOKEN_EXPIRED', message: 'Expired', timestamp: '' } }),
    )
    await expect(api.get('/me')).rejects.toMatchObject({ status: 401 })
    expect(handler).toHaveBeenCalledTimes(1)
    expect(tokenStorage.hasSession()).toBe(false)
  })

  it('on 401 without a session (e.g. wrong password): does not trigger the handler', async () => {
    const { api, fetchMock, setUnauthorizedHandler } = await setup()
    const handler = vi.fn<(error: unknown) => void>()
    setUnauthorizedHandler(handler)
    fetchMock.mockResolvedValueOnce(
      json(401, { error: { code: 'INVALID_CREDENTIALS', message: 'x', timestamp: '' } }),
    )
    await expect(api.post('/auth/login', {})).rejects.toMatchObject({ status: 401 })
    expect(handler).not.toHaveBeenCalled()
  })
})

describe('resolveApiUrl', () => {
  it('resolves host-relative paths and passes safe absolute URLs through', async () => {
    const { resolveApiUrl } = await setup()
    expect(resolveApiUrl('/static/frames/a.webp')).toBe('/static/frames/a.webp')
    expect(resolveApiUrl('static/a.webp')).toBe('/static/a.webp')
    expect(resolveApiUrl('https://cdn.example.com/a.webp')).toBe('https://cdn.example.com/a.webp')
    expect(resolveApiUrl('data:image/png;base64,AAAA')).toBe('data:image/png;base64,AAAA')
    expect(resolveApiUrl(null)).toBeUndefined()
    expect(resolveApiUrl('   ')).toBeUndefined()
  })

  it.each([
    'javascript:alert(1)',
    'JavaScript:alert(1)',
    ' javascript:alert(1)',
    'data:text/html,<script>x</script>',
  ])('neutralises executable URL %j into a same-origin path', async (url) => {
    const { resolveApiUrl } = await setup()
    const resolved = resolveApiUrl(url)
    expect(resolved?.startsWith('/')).toBe(true)
    expect(resolved).not.toMatch(/^\s*(javascript|data):/i)
  })
})

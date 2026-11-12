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

const UNAUTHORIZED = { error: { code: 'TOKEN_EXPIRED', message: 'Expired', timestamp: '' } }
const NEW_TOKENS = { access_token: 'fresh', token_type: 'bearer', expires_in: 900 }
const isRefresh = (url: unknown) => String(url).endsWith('/auth/refresh')

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

  it('on 401 with a session whose refresh is rejected: clears tokens, calls the handler once', async () => {
    const { api, fetchMock, setUnauthorizedHandler, tokenStorage } = await setup({
      accessToken: 'tok',
      expiresAt: Date.now() + 60_000,
    })
    const handler = vi.fn<(error: unknown) => void>()
    setUnauthorizedHandler(handler)
    fetchMock.mockImplementation(async (url) =>
      String(url).endsWith('/auth/refresh') ? json(401, UNAUTHORIZED) : json(401, UNAUTHORIZED),
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

describe('session refresh', () => {
  const live = { accessToken: 'old', expiresAt: Date.now() + 60_000 }

  it('renews the token on 401 and replays the request once with the new bearer', async () => {
    const { api, fetchMock, tokenStorage } = await setup(live)
    fetchMock.mockImplementation(async (url, init) => {
      if (isRefresh(url)) return json(200, NEW_TOKENS)
      const auth = new Headers(init?.headers).get('Authorization')
      return auth === 'Bearer fresh' ? json(200, { ok: true }) : json(401, UNAUTHORIZED)
    })
    await expect(api.get('/designs')).resolves.toEqual({ ok: true })
    expect(tokenStorage.getAccessToken()).toBe('fresh')
    const calls = fetchMock.mock.calls.map(([url]) => String(url))
    expect(calls).toEqual(['/api/v1/designs', '/api/v1/auth/refresh', '/api/v1/designs'])
    // The refresh call carries the CSRF header and the cookie, but no bearer token.
    const refreshInit = fetchMock.mock.calls[1]?.[1]
    expect(new Headers(refreshInit?.headers).get('X-CSRF-Protection')).toBe('1')
    expect(new Headers(refreshInit?.headers).has('Authorization')).toBe(false)
    expect(refreshInit?.credentials).toBe('include')
  })

  it('shares one refresh between concurrent 401s (no double rotation)', async () => {
    const { api, fetchMock } = await setup(live)
    let refreshes = 0
    fetchMock.mockImplementation(async (url, init) => {
      if (isRefresh(url)) {
        refreshes += 1
        await new Promise((r) => setTimeout(r, 10))
        return json(200, NEW_TOKENS)
      }
      return new Headers(init?.headers).get('Authorization') === 'Bearer fresh'
        ? json(200, { ok: true })
        : json(401, UNAUTHORIZED)
    })
    await Promise.all([api.get('/a'), api.get('/b'), api.get('/c')])
    expect(refreshes).toBe(1)
  })

  it('renews an already-expired token before sending, so no request is wasted on a 401', async () => {
    const { api, fetchMock } = await setup({ accessToken: 'old', expiresAt: Date.now() - 1 })
    fetchMock.mockImplementation(async (url) =>
      isRefresh(url) ? json(200, NEW_TOKENS) : json(200, { ok: true }),
    )
    await api.get('/designs')
    expect(fetchMock.mock.calls.map(([url]) => String(url))).toEqual([
      '/api/v1/auth/refresh',
      '/api/v1/designs',
    ])
    expect(new Headers(fetchMock.mock.calls[1]?.[1]?.headers).get('Authorization')).toBe('Bearer fresh')
  })

  it('does not loop: a 401 on the replay ends the session', async () => {
    const { api, fetchMock, setUnauthorizedHandler, tokenStorage } = await setup(live)
    const handler = vi.fn<(error: unknown) => void>()
    setUnauthorizedHandler(handler)
    fetchMock.mockImplementation(async (url) =>
      isRefresh(url) ? json(200, NEW_TOKENS) : json(401, UNAUTHORIZED),
    )
    await expect(api.get('/designs')).rejects.toMatchObject({ status: 401 })
    expect(fetchMock.mock.calls.filter(([url]) => isRefresh(url))).toHaveLength(1)
    expect(handler).toHaveBeenCalledTimes(1)
    expect(tokenStorage.hasSession()).toBe(false)
  })

  it('keeps the session when the refresh fails for network reasons', async () => {
    const { api, fetchMock, tokenStorage, setUnauthorizedHandler } = await setup(live)
    const handler = vi.fn<(error: unknown) => void>()
    setUnauthorizedHandler(handler)
    fetchMock.mockImplementation(async (url) => {
      if (isRefresh(url)) throw new TypeError('Failed to fetch')
      return json(401, UNAUTHORIZED)
    })
    await expect(api.get('/designs')).rejects.toMatchObject({ code: 'NETWORK_ERROR' })
    expect(handler).not.toHaveBeenCalled()
    expect(tokenStorage.hasSession()).toBe(true)
  })

  it('never refreshes for public calls or when no session existed (wrong password)', async () => {
    const { api, fetchMock } = await setup()
    fetchMock.mockImplementation(async () => json(401, UNAUTHORIZED))
    await expect(api.post('/auth/login', {}, { auth: false })).rejects.toMatchObject({ status: 401 })
    await expect(api.get('/me')).rejects.toMatchObject({ status: 401 })
    expect(fetchMock.mock.calls.some(([url]) => isRefresh(url))).toBe(false)
  })

  it('refreshSession reports a rejected cookie as false and stores nothing', async () => {
    const { refreshSession, fetchMock, tokenStorage } = await setup()
    fetchMock.mockResolvedValueOnce(json(401, UNAUTHORIZED))
    await expect(refreshSession()).resolves.toBe(false)
    expect(tokenStorage.getAccessToken()).toBeNull()
    fetchMock.mockResolvedValueOnce(json(200, NEW_TOKENS))
    await expect(refreshSession()).resolves.toBe(true)
    expect(tokenStorage.getAccessToken()).toBe('fresh')
  })
})

function xhrAt(index: number): FakeXhr {
  const xhr = FakeXhr.instances[index]
  if (!xhr) throw new Error(`no request #${index}`)
  return xhr
}

class FakeXhr {
  static instances: FakeXhr[] = []
  method = ''
  url = ''
  headers: Record<string, string> = {}
  withCredentials = false
  body: unknown = null
  status = 0
  responseText = ''
  upload: { onprogress: ((e: { lengthComputable: boolean; loaded: number; total: number }) => void) | null } =
    {
      onprogress: null,
    }
  onload: (() => void) | null = null
  onerror: (() => void) | null = null
  onabort: (() => void) | null = null
  constructor() {
    FakeXhr.instances.push(this)
  }
  open(method: string, url: string) {
    this.method = method
    this.url = url
  }
  setRequestHeader(name: string, value: string) {
    this.headers[name] = value
  }
  send(body: unknown) {
    this.body = body
  }
  abort() {
    this.onabort?.()
  }
  respond(status: number, body: unknown) {
    this.status = status
    this.responseText = JSON.stringify(body)
    this.onload?.()
  }
}

describe('uploadFile', () => {
  const tick = () => new Promise((r) => setTimeout(r, 0))
  const blob = new Blob(['x'], { type: 'image/png' })

  async function start(session?: { accessToken: string; expiresAt: number }) {
    FakeXhr.instances = []
    const ctx = await setup(session)
    vi.stubGlobal('XMLHttpRequest', FakeXhr)
    return ctx
  }

  it('posts multipart with the bearer token, CSRF header and cookies, and reports progress', async () => {
    const { uploadFile } = await start({ accessToken: 'tok', expiresAt: Date.now() + 60_000 })
    const progress: number[] = []
    const promise = uploadFile<{ id: string }>('/photos/upload', blob, 'a.png', {
      onProgress: (p) => progress.push(p),
    })
    const xhr = xhrAt(0)
    expect(xhr).toMatchObject({ method: 'POST', url: '/api/v1/photos/upload', withCredentials: true })
    expect(xhr.headers).toMatchObject({ Authorization: 'Bearer tok', 'X-CSRF-Protection': '1' })
    expect(xhr.body).toBeInstanceOf(FormData)
    expect((xhr.body as FormData).get('file')).toBeInstanceOf(Blob)
    xhr.upload.onprogress?.({ lengthComputable: true, loaded: 5, total: 10 })
    xhr.upload.onprogress?.({ lengthComputable: false, loaded: 5, total: 0 })
    xhr.respond(201, { id: 'p1' })
    await expect(promise).resolves.toEqual({ id: 'p1' })
    expect(progress).toEqual([0.5])
  })

  it('turns failures into ApiError without leaking server text', async () => {
    const { uploadFile } = await start({ accessToken: 'tok', expiresAt: Date.now() + 60_000 })
    const promise = uploadFile('/photos/upload', blob, 'a.png')
    xhrAt(0).respond(422, {
      error: {
        code: 'VALIDATION_ERROR',
        message: 'Too small',
        details: [{ field: 'file', issue: 'Too small' }],
        timestamp: '',
      },
    })
    await expect(promise).rejects.toMatchObject({
      status: 422,
      code: 'VALIDATION_ERROR',
      fieldErrors: { file: 'Too small' },
    })

    const net = uploadFile('/photos/upload', blob, 'a.png')
    xhrAt(1).onerror?.()
    await expect(net).rejects.toMatchObject({ code: 'NETWORK_ERROR', status: 0 })
  })

  it('renews the access token once on 401 and retries the upload', async () => {
    const { uploadFile, fetchMock } = await start({ accessToken: 'old', expiresAt: Date.now() + 60_000 })
    fetchMock.mockResolvedValue(json(200, NEW_TOKENS))
    const promise = uploadFile<{ id: string }>('/photos/upload', blob, 'a.png')
    xhrAt(0).respond(401, UNAUTHORIZED)
    await tick()
    await tick()
    expect(isRefresh(fetchMock.mock.calls[0]?.[0])).toBe(true)
    const retry = xhrAt(1)
    expect(retry.headers.Authorization).toBe('Bearer fresh')
    retry.respond(201, { id: 'p2' })
    await expect(promise).resolves.toEqual({ id: 'p2' })
  })

  it('ends the session when the retry is rejected too', async () => {
    const { uploadFile, fetchMock, setUnauthorizedHandler, tokenStorage } = await start({
      accessToken: 'old',
      expiresAt: Date.now() + 60_000,
    })
    const handler = vi.fn<(error: unknown) => void>()
    setUnauthorizedHandler(handler)
    fetchMock.mockResolvedValue(json(200, NEW_TOKENS))
    const promise = uploadFile('/photos/upload', blob, 'a.png')
    xhrAt(0).respond(401, UNAUTHORIZED)
    await tick()
    await tick()
    xhrAt(1).respond(401, UNAUTHORIZED)
    await expect(promise).rejects.toMatchObject({ status: 401 })
    expect(handler).toHaveBeenCalledTimes(1)
    expect(tokenStorage.hasSession()).toBe(false)
  })

  it('can be cancelled', async () => {
    const { uploadFile } = await start({ accessToken: 'tok', expiresAt: Date.now() + 60_000 })
    const controller = new AbortController()
    const promise = uploadFile('/photos/upload', blob, 'a.png', { signal: controller.signal })
    controller.abort()
    await expect(promise).rejects.toMatchObject({ name: 'AbortError' })
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

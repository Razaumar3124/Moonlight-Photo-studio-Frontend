import { env } from '@/config/env'
import type { ApiErrorCode, ApiErrorDetail, ApiErrorEnvelope, AuthTokens } from '@/types/api'
import { endpoints } from './endpoints'
import { tokenStorage } from './tokenStorage'

/* ================================== Errors ================================== */

/** Client-side codes for failures that never reached (or never came back from) the API. */
export type ClientErrorCode = 'NETWORK_ERROR' | 'INVALID_RESPONSE' | 'UNKNOWN_ERROR'

/**
 * Every failed request throws this. It is normalised from the contract's error envelope
 * `{ error: { code, message, details[], timestamp } }`, and also from FastAPI's default
 * `{ detail }` shape in case a handler bypasses the envelope (see API_ALIGNMENT.md Q11).
 */
export class ApiError extends Error {
  readonly status: number
  readonly code: ApiErrorCode | ClientErrorCode
  readonly details: ApiErrorDetail[]
  readonly timestamp: string | null

  constructor(init: {
    status: number
    code: ApiErrorCode | ClientErrorCode
    message: string
    details?: ApiErrorDetail[]
    timestamp?: string | null
    cause?: unknown
  }) {
    super(init.message, { cause: init.cause })
    this.name = 'ApiError'
    this.status = init.status
    this.code = init.code
    this.details = init.details ?? []
    this.timestamp = init.timestamp ?? null
  }

  get isUnauthorized() {
    return this.status === 401
  }

  get isValidationError() {
    return this.status === 422 || this.status === 400
  }

  get isNetworkError() {
    return this.code === 'NETWORK_ERROR'
  }

  /** `details` keyed by field, for showing inline form errors: `{ email: 'Already registered' }`. */
  get fieldErrors(): Record<string, string> {
    const out: Record<string, string> = {}
    for (const { field, issue } of this.details) {
      if (field && !(field in out)) out[field] = issue
    }
    return out
  }
}

export function isApiError(value: unknown): value is ApiError {
  return value instanceof ApiError
}

function isEnvelope(data: unknown): data is ApiErrorEnvelope {
  if (typeof data !== 'object' || data === null || !('error' in data)) return false
  const error = (data as { error: unknown }).error
  return typeof error === 'object' && error !== null && 'code' in error && 'message' in error
}

interface FastApiValidationItem {
  loc: (string | number)[]
  msg: string
}

/** Turn any error body into an ApiError. */
function toApiError(status: number, data: unknown): ApiError {
  if (isEnvelope(data)) {
    const { code, message, details, timestamp } = data.error
    return new ApiError({ status, code, message, details, timestamp })
  }

  // Fallback: FastAPI default `{ detail: string | ValidationItem[] }`
  const detail = (data as { detail?: unknown } | null)?.detail
  if (Array.isArray(detail)) {
    const details = (detail as FastApiValidationItem[]).map((item) => ({
      // ['body', 'email'] → 'email'; nested → 'frames.0.x_inches'
      field: item.loc.filter((part) => part !== 'body' && part !== 'query').join('.'),
      issue: item.msg,
    }))
    return new ApiError({ status, code: 'VALIDATION_ERROR', message: 'Some fields are invalid.', details })
  }
  if (typeof detail === 'string') {
    return new ApiError({ status, code: `HTTP_${status}`, message: detail })
  }

  return new ApiError({
    status,
    code: status >= 500 ? 'INTERNAL_ERROR' : 'UNKNOWN_ERROR',
    message:
      status >= 500 ? 'Something went wrong on our side. Please try again.' : `Request failed (${status}).`,
  })
}

/* ============================== 401 handling ================================ */

type UnauthorizedHandler = (error: ApiError) => void
let unauthorizedHandler: UnauthorizedHandler | null = null

/**
 * Register what happens when the session is lost: an authenticated request still gets a 401 after
 * a refresh attempt (e.g. show the sign-in page). Set once by the auth layer. The access token is
 * cleared before it runs.
 */
export function setUnauthorizedHandler(handler: UnauthorizedHandler | null) {
  unauthorizedHandler = handler
}

/* ================================ Requests ================================== */

export type QueryValue = string | number | boolean | null | undefined
export type QueryParams = Record<string, QueryValue | QueryValue[]>

export interface RequestOptions extends Omit<RequestInit, 'body' | 'method'> {
  /** JSON-serialisable body, or FormData for uploads. */
  body?: unknown
  /** Appended as a query string. `undefined`/`null` values are skipped. */
  query?: QueryParams
  /** Attach the Bearer token if one exists. Default true; harmless on public endpoints. */
  auth?: boolean
  /**
   * With `auth`, renew an expired/rejected access token through the refresh cookie and retry once
   * (default true). The refresh call itself turns this off.
   */
  refresh?: boolean
}

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

/**
 * Sent on every state-changing request. The backend requires it on the endpoints that use the
 * refresh cookie; a cross-site page can't add custom headers without passing CORS (CSRF defence).
 */
export const CSRF_HEADER = 'X-CSRF-Protection'

function buildUrl(path: string, query?: QueryParams): string {
  const url = `${env.apiBaseUrl}${path.startsWith('/') ? path : `/${path}`}`
  if (!query) return url

  const params = new URLSearchParams()
  for (const [key, raw] of Object.entries(query)) {
    for (const value of Array.isArray(raw) ? raw : [raw]) {
      if (value !== undefined && value !== null) params.append(key, String(value))
    }
  }
  const qs = params.toString()
  return qs ? `${url}?${qs}` : url
}

/* ============================ Session refresh =============================== */

let refreshInFlight: Promise<boolean> | null = null

/**
 * Exchange the httpOnly refresh cookie for a new access token (the backend rotates the cookie).
 * Single-flight: concurrent callers (parallel requests, React StrictMode) share one network call,
 * because rotating the same cookie twice at once would needlessly race.
 *
 * Resolves `true` when a new access token is stored, `false` when the server rejected the cookie
 * (no/expired/revoked session; local state is cleared). Rejects with a network/server error
 * otherwise, in which case the session may still be valid and is left untouched.
 */
export function refreshSession(): Promise<boolean> {
  refreshInFlight ??= (async () => {
    try {
      const tokens = await apiRequest<AuthTokens>('POST', endpoints.auth.refresh, {
        auth: false,
        refresh: false,
      })
      tokenStorage.save(tokens)
      return tokenStorage.getAccessToken() !== null
    } catch (error) {
      if (isApiError(error) && (error.status === 401 || error.status === 403)) {
        tokenStorage.clear()
        return false
      }
      throw error
    } finally {
      refreshInFlight = null
    }
  })()
  return refreshInFlight
}

export async function apiRequest<T>(
  method: HttpMethod,
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { auth = true, refresh = true } = options
  // An expired token is not sent, but the resulting 401 should still end the session.
  const hadSession = auth && tokenStorage.hasSession()
  const canRefresh = auth && refresh && hadSession

  // Known-expired access token: renew first instead of sending a request that must 401.
  if (canRefresh && !tokenStorage.getAccessToken()) {
    try {
      await refreshSession()
    } catch {
      // Offline/server trouble: send the request anyway; it fails on its own terms.
    }
  }

  const sentToken = auth ? tokenStorage.getAccessToken() : null
  try {
    return await send<T>(method, path, options, sentToken)
  } catch (error) {
    if (!(isApiError(error) && error.isUnauthorized && auth)) throw error

    if (canRefresh) {
      // 401 on a token we sent: renew once and replay. If another request already renewed it
      // (the current token differs from the one that failed), just replay.
      const current = tokenStorage.getAccessToken()
      const renewed = current && current !== sentToken ? true : await refreshSession()
      if (renewed) {
        try {
          return await send<T>(method, path, options, tokenStorage.getAccessToken())
        } catch (retryError) {
          if (isApiError(retryError) && retryError.isUnauthorized) endSession(retryError)
          throw retryError
        }
      }
    }
    if (hadSession) endSession(error)
    throw error
  }
}

function endSession(error: ApiError) {
  tokenStorage.clear()
  unauthorizedHandler?.(error)
}

async function send<T>(
  method: HttpMethod,
  path: string,
  { body, query, headers, auth: _auth, refresh: _refresh, ...init }: RequestOptions,
  token: string | null,
): Promise<T> {
  const isFormData = body instanceof FormData

  // `new Headers()` accepts every HeadersInit form (object, array, Headers instance);
  // object-spreading a Headers instance would silently drop all of its entries.
  const requestHeaders = new Headers(headers)
  if (!requestHeaders.has('Accept')) requestHeaders.set('Accept', 'application/json')
  // Let the browser set the multipart boundary for FormData.
  if (body !== undefined && !isFormData && !requestHeaders.has('Content-Type')) {
    requestHeaders.set('Content-Type', 'application/json')
  }
  if (token && !requestHeaders.has('Authorization')) requestHeaders.set('Authorization', `Bearer ${token}`)
  if (method !== 'GET' && !requestHeaders.has(CSRF_HEADER)) requestHeaders.set(CSRF_HEADER, '1')

  let response: Response
  try {
    response = await fetch(buildUrl(path, query), {
      // The refresh cookie must also reach a cross-origin API (production); CORS on the API
      // only allows the configured frontend origins with credentials.
      credentials: 'include',
      ...init,
      method,
      headers: requestHeaders,
      body: body === undefined ? undefined : isFormData ? body : JSON.stringify(body),
    })
  } catch (cause) {
    // Let aborts propagate untouched so callers can ignore them.
    if (cause instanceof DOMException && cause.name === 'AbortError') throw cause
    throw new ApiError({
      status: 0,
      code: 'NETWORK_ERROR',
      message: 'Unable to reach the server. Check your connection and try again.',
      cause,
    })
  }

  // 204 No Content (deletes) or an empty 201/200.
  const text = response.status === 204 ? '' : await response.text()
  let data: unknown = undefined
  if (text) {
    try {
      data = JSON.parse(text)
    } catch (cause) {
      if (response.ok) {
        throw new ApiError({
          status: response.status,
          code: 'INVALID_RESPONSE',
          message: 'Unexpected response from server.',
          cause,
        })
      }
    }
  }

  if (!response.ok) throw toApiError(response.status, data)

  return data as T
}

/**
 * Typed HTTP helpers. Paths come from `endpoints.ts`; response types from `@/types/api`.
 * @example api.get<ListResponse<LayoutTemplate>>(endpoints.templates.list, { query: { category: 'grid' } })
 */
export const api = {
  get: <T>(path: string, options?: Omit<RequestOptions, 'body'>) => apiRequest<T>('GET', path, options),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiRequest<T>('POST', path, { ...options, body }),
  put: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiRequest<T>('PUT', path, { ...options, body }),
  patch: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    apiRequest<T>('PATCH', path, { ...options, body }),
  delete: <T = void>(path: string, options?: Omit<RequestOptions, 'body'>) =>
    apiRequest<T>('DELETE', path, options),
  /** multipart/form-data upload, e.g. `api.upload<Photo>(endpoints.photos.upload, { file })`. */
  upload: <T>(
    path: string,
    fields: Record<string, Blob | string>,
    options?: Omit<RequestOptions, 'body'>,
  ) => {
    const form = new FormData()
    for (const [key, value] of Object.entries(fields)) form.append(key, value)
    return apiRequest<T>('POST', path, { ...options, body: form })
  },
}

/* ============================== URL helpers ================================= */

/**
 * The API returns host-relative URLs (`/static/frames/x.webp`, `/api/v1/photos/101/thumbnail`).
 * Resolve them against the API origin so they work whether the API is same-origin (dev proxy)
 * or on another host in production.
 *
 * Only http(s), protocol-relative, `blob:` and `data:image/…` URLs pass through unchanged. Anything
 * else (e.g. `javascript:`, `data:text/html`) is treated as a path on the API host, so a
 * malicious value can never become an executable link.
 */
export function resolveApiUrl(url: string | null | undefined): string | undefined {
  const value = url?.trim()
  if (!value) return undefined
  if (/^(https?:)?\/\//i.test(value) || /^blob:/i.test(value) || /^data:image\//i.test(value)) return value
  const base = /^https?:\/\//i.test(env.apiBaseUrl) ? new URL(env.apiBaseUrl).origin : ''
  return `${base}/${value.replace(/^\/+/, '')}`
}

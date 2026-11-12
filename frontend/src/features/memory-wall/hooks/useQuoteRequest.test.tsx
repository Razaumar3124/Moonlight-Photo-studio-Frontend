// @vitest-environment jsdom
import { act, cleanup, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/services/apiClient'
import { quotesService } from '@/services/quotesService'
import type { QuotePrepareResponse } from '@/types/api'
import { NEW_DESIGN, sessionFor, type DesignSession } from '../lib/designSave'
import { renderWallImage } from '../lib/exportImage'
import { buildScene } from '../lib/geometry/scene'
import { createInitialState, plannerReducer, type PlannerState } from '../lib/plannerState'
import { useQuoteRequest, type QuoteRequestDeps } from './useQuoteRequest'

vi.mock('@/services/quotesService', () => ({
  quotesService: { prepare: vi.fn<() => Promise<unknown>>() },
}))
vi.mock('../lib/exportImage', () => ({
  renderWallImage: vi.fn<() => Promise<Blob>>(),
}))

const prepare = vi.mocked(quotesService.prepare)
const render = vi.mocked(renderWallImage)
const DESIGN_ID = '665f1c2e9b1d4a00aaaaaaaa'
const TOKEN = 'LDcWktm_9DuGs9LEC5SGRMBedXLRnZgGj2tq5Zumqp8'

const okResponse = (over: Partial<QuotePrepareResponse> = {}): QuotePrepareResponse => ({
  quote_id: 'MQ-2026-0001',
  status: 'draft',
  whatsapp_url: 'https://wa.me/919800000001?text=Hello',
  report_url: `http://localhost:5173/q/${TOKEN}`,
  expires_at: '2026-12-12T00:00:00Z',
  ...over,
})

const png = (size = 1000) => new Blob([new Uint8Array(size)], { type: 'image/png' })

function setup(overrides: Partial<QuoteRequestDeps> = {}) {
  const state: PlannerState = { ...createInitialState(), title: 'My Wall' }
  const session: DesignSession = sessionFor(DESIGN_ID, 1, state)
  const ensureSaved = vi.fn<(title: string) => Promise<DesignSession>>(async () => session)
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
  const deps: QuoteRequestDeps = {
    state,
    scene: buildScene(state),
    session,
    needsSave: false,
    svgRef: { current: svg },
    ensureSaved,
    ...overrides,
  }
  const hook = renderHook((props: QuoteRequestDeps) => useQuoteRequest(props), { initialProps: deps })
  return { hook, deps, ensureSaved, state, session }
}

beforeEach(() => {
  vi.resetAllMocks()
  render.mockResolvedValue(png())
  prepare.mockResolvedValue(okResponse())
})
afterEach(cleanup)

const keyOf = (call: number) => prepare.mock.calls[call]?.[2]

describe('happy path', () => {
  it('prepares the quote for the saved design without saving again', async () => {
    const { hook, ensureSaved } = setup()
    act(() => hook.result.current.open())
    expect(hook.result.current.step).toBe('confirm')
    await act(() => hook.result.current.submit('My Wall'))
    expect(ensureSaved).not.toHaveBeenCalled()
    expect(hook.result.current.step).toBe('ready')
    expect(hook.result.current.result).toEqual({
      quoteId: 'MQ-2026-0001',
      whatsappUrl: 'https://wa.me/919800000001?text=Hello',
      reportUrl: `http://localhost:5173/q/${TOKEN}`,
    })
    const [designData, preview, key] = prepare.mock.calls[0] ?? []
    expect(designData).toMatchObject({ designId: DESIGN_ID, title: 'My Wall', frames: expect.any(Array) })
    expect(preview).toBeInstanceOf(Blob)
    expect(key).toMatch(/^[A-Za-z0-9_-]{8,64}$/)
  })

  it('renders the preview with dimension guides from the wall on screen', async () => {
    const { hook } = setup()
    act(() => hook.result.current.open())
    await act(() => hook.result.current.submit('My Wall'))
    expect(render).toHaveBeenCalledTimes(1)
    expect(render.mock.calls[0]?.[2]).toMatchObject({
      title: 'My Wall',
      unit: 'ft',
      guides: true,
      format: 'image/png',
    })
  })
})

describe('save first', () => {
  it('saves unsaved changes before preparing the quote, and quotes the saved design', async () => {
    const order: string[] = []
    const fresh = createInitialState()
    const saved = sessionFor(DESIGN_ID, 2, fresh)
    const ensureSaved = vi.fn<(title: string) => Promise<DesignSession>>(async () => {
      order.push('save')
      return saved
    })
    prepare.mockImplementation(async () => {
      order.push('prepare')
      return okResponse()
    })
    const { hook } = setup({ needsSave: true, session: NEW_DESIGN, ensureSaved, state: fresh })
    act(() => hook.result.current.open())
    await act(() => hook.result.current.submit('Named Wall'))
    expect(ensureSaved).toHaveBeenCalledWith('Named Wall')
    expect(order).toEqual(['save', 'prepare'])
    expect(prepare.mock.calls[0]?.[0]).toMatchObject({ designId: DESIGN_ID, title: 'Named Wall' })
  })

  it('stops with a clear message when saving fails, and sends no quote', async () => {
    const ensureSaved = vi.fn<(title: string) => Promise<DesignSession>>(async () => {
      throw new ApiError({ status: 0, code: 'NETWORK_ERROR', message: 'x' })
    })
    const { hook } = setup({ needsSave: true, session: NEW_DESIGN, ensureSaved })
    act(() => hook.result.current.open())
    await act(() => hook.result.current.submit('My Wall'))
    expect(hook.result.current.step).toBe('error')
    expect(hook.result.current.problem?.message).toMatch(/offline/)
    expect(prepare).not.toHaveBeenCalled()
    expect(render).not.toHaveBeenCalled()
  })

  it('does not offer a retry for a layout the server refuses to save', async () => {
    const ensureSaved = vi.fn<(title: string) => Promise<DesignSession>>(async () => {
      throw new ApiError({
        status: 422,
        code: 'VALIDATION_ERROR',
        message: 'x',
        details: [{ field: 'items.f1', issue: 'Frames overlap' }],
      })
    })
    const { hook } = setup({ needsSave: true, ensureSaved })
    act(() => hook.result.current.open())
    await act(() => hook.result.current.submit('My Wall'))
    expect(hook.result.current.problem?.retryable).toBe(false)
  })
})

describe('no duplicate quotes', () => {
  it('collapses a double click into one request', async () => {
    let release: (r: QuotePrepareResponse) => void = () => undefined
    prepare.mockReturnValue(new Promise((resolve) => (release = resolve)))
    const { hook } = setup()
    act(() => hook.result.current.open())
    await act(async () => {
      const first = hook.result.current.submit('My Wall')
      const second = hook.result.current.submit('My Wall')
      await Promise.resolve()
      release(okResponse())
      await Promise.all([first, second])
    })
    expect(prepare).toHaveBeenCalledTimes(1)
    expect(hook.result.current.step).toBe('ready')
  })

  it('retries a failed request with the SAME idempotency key and the same rendered preview', async () => {
    prepare.mockRejectedValueOnce(new ApiError({ status: 0, code: 'NETWORK_ERROR', message: 'x' }))
    const { hook } = setup()
    act(() => hook.result.current.open())
    await act(() => hook.result.current.submit('My Wall'))
    expect(hook.result.current.step).toBe('error')
    expect(hook.result.current.problem?.retryable).toBe(true)
    await act(() => hook.result.current.retry())
    expect(hook.result.current.step).toBe('ready')
    expect(prepare).toHaveBeenCalledTimes(2)
    expect(keyOf(1)).toBe(keyOf(0))
    expect(prepare.mock.calls[1]?.[1]).toBe(prepare.mock.calls[0]?.[1])
    expect(render).toHaveBeenCalledTimes(1)
  })

  it('reopening the dialog shows the existing quote instead of creating another', async () => {
    const { hook } = setup()
    act(() => hook.result.current.open())
    await act(() => hook.result.current.submit('My Wall'))
    act(() => hook.result.current.close())
    act(() => hook.result.current.open())
    expect(hook.result.current.step).toBe('ready')
    expect(hook.result.current.result?.quoteId).toBe('MQ-2026-0001')
    expect(prepare).toHaveBeenCalledTimes(1)
  })

  it('a changed design starts a new attempt with a new key', async () => {
    const { hook, deps } = setup()
    act(() => hook.result.current.open())
    await act(() => hook.result.current.submit('My Wall'))
    const changed = plannerReducer(deps.state, {
      type: 'frames/updateMount',
      index: 0,
      patch: { marginIn: 4 },
    })
    const session = sessionFor(DESIGN_ID, 2, changed)
    hook.rerender({ ...deps, state: changed, scene: buildScene(changed), session })
    act(() => hook.result.current.close())
    act(() => hook.result.current.open())
    expect(hook.result.current.step).toBe('confirm') // not the old quote
    await act(() => hook.result.current.submit('My Wall'))
    expect(prepare).toHaveBeenCalledTimes(2)
    expect(keyOf(1)).not.toBe(keyOf(0))
    expect(render).toHaveBeenCalledTimes(2)
  })

  it('"start new" forgets the quote and uses a new key', async () => {
    const { hook } = setup()
    act(() => hook.result.current.open())
    await act(() => hook.result.current.submit('My Wall'))
    act(() => hook.result.current.startNew())
    expect(hook.result.current.step).toBe('confirm')
    await act(() => hook.result.current.submit('My Wall'))
    expect(keyOf(1)).not.toBe(keyOf(0))
  })

  it('cannot be closed while it is working', async () => {
    let release: (r: QuotePrepareResponse) => void = () => undefined
    prepare.mockReturnValue(new Promise((resolve) => (release = resolve)))
    const { hook } = setup()
    act(() => hook.result.current.open())
    let pending: Promise<void> = Promise.resolve()
    await act(async () => {
      pending = hook.result.current.submit('My Wall')
      await Promise.resolve()
      await Promise.resolve()
    })
    act(() => hook.result.current.close())
    expect(hook.result.current.step).not.toBe('closed')
    await act(async () => {
      release(okResponse())
      await pending
    })
    expect(hook.result.current.step).toBe('ready')
  })
})

describe('failures', () => {
  it('shows a safe message for a failed request and keeps the preview for the retry', async () => {
    prepare.mockRejectedValueOnce(
      new ApiError({ status: 503, code: 'STORAGE_UNAVAILABLE', message: 'Traceback…' }),
    )
    const { hook } = setup()
    act(() => hook.result.current.open())
    await act(() => hook.result.current.submit('My Wall'))
    expect(hook.result.current.problem?.message).toMatch(/busy/)
    expect(JSON.stringify(hook.result.current.problem)).not.toMatch(/Traceback/)
  })

  it('refuses links that are not WhatsApp / our own report, and lets the user retry', async () => {
    prepare.mockResolvedValueOnce(okResponse({ whatsapp_url: 'javascript:alert(1)' }))
    const { hook } = setup()
    act(() => hook.result.current.open())
    await act(() => hook.result.current.submit('My Wall'))
    expect(hook.result.current.step).toBe('error')
    expect(hook.result.current.result).toBeNull()
    prepare.mockResolvedValueOnce(okResponse({ report_url: 'https://evil.example/q/x' }))
    await act(() => hook.result.current.retry())
    expect(hook.result.current.step).toBe('error')
    await act(() => hook.result.current.retry())
    expect(hook.result.current.step).toBe('ready')
  })

  it('falls back to WebP when a PNG would be too big, and gives up if even that is', async () => {
    render.mockResolvedValueOnce(png(13 * 1024 * 1024)).mockResolvedValueOnce(png(500))
    const { hook } = setup()
    act(() => hook.result.current.open())
    await act(() => hook.result.current.submit('My Wall'))
    expect(render.mock.calls.map((c) => c[2]?.format)).toEqual(['image/png', 'image/webp'])
    expect(hook.result.current.step).toBe('ready')

    cleanup()
    vi.clearAllMocks()
    render.mockResolvedValue(png(13 * 1024 * 1024))
    const second = setup()
    act(() => second.hook.result.current.open())
    await act(() => second.hook.result.current.submit('My Wall'))
    expect(second.hook.result.current.step).toBe('error')
    expect(prepare).not.toHaveBeenCalled()
  })

  it('reports a failed preview render without creating a quote', async () => {
    render.mockRejectedValue(new Error('canvas'))
    const { hook } = setup()
    act(() => hook.result.current.open())
    await act(() => hook.result.current.submit('My Wall'))
    expect(hook.result.current.step).toBe('error')
    expect(hook.result.current.problem?.retryable).toBe(true)
    expect(prepare).not.toHaveBeenCalled()
  })

  it('reports an expired session from the API', async () => {
    prepare.mockRejectedValueOnce(new ApiError({ status: 401, code: 'TOKEN_REVOKED', message: 'x' }))
    const { hook } = setup()
    act(() => hook.result.current.open())
    await act(() => hook.result.current.submit('My Wall'))
    expect(hook.result.current.problem?.message).toMatch(/session ended/)
  })
})

// @vitest-environment jsdom
import { describe, expect, it } from 'vitest'
import { ApiError } from '@/services/apiClient'
import { itemIds, toVersionRequest } from './designMapper'
import { buildScene } from './geometry/scene'
import { createInitialState, plannerReducer } from './plannerState'
import {
  buildQuoteDesignData,
  describeQuoteError,
  safeReportUrl,
  safeWhatsAppUrl,
  whatsAppMessage,
  whatsAppNumber,
} from './quoteRequest'

const DESIGN_ID = '665f1c2e9b1d4a00aaaaaaaa'
const PHOTO = '665f1c2e9b1d4a0012345678'
const must = <T>(v: T | undefined): T => {
  if (v === undefined) throw new Error('missing')
  return v
}

describe('buildQuoteDesignData', () => {
  it('describes the wall, layout and frames of the planner, tied to the saved design', () => {
    const state = createInitialState()
    const data = buildQuoteDesignData(state, buildScene(state), DESIGN_ID)
    expect(data).toMatchObject({
      title: 'Living Room Gallery Wall',
      designId: DESIGN_ID,
      displayUnit: 'ft',
      preview: { sofa: true },
      wall: { widthIn: 144, heightIn: 108, paintId: 'warm-cream' },
      layout: { style: 'grid', gapIn: 3 },
    })
    expect(data.frames).toHaveLength(9)
    expect(data.frames[0]).toMatchObject({
      sizeId: '12x16',
      orientation: 'portrait',
      finishId: 'natural-oak',
      mount: { enabled: true, colourId: 'museum-white', marginIn: 2 },
    })
  })

  it('uses the same frame ids and photos as the saved version, so the server finds them identical', () => {
    let state = createInitialState()
    state = plannerReducer(state, {
      type: 'frames/setPhoto',
      frameId: must(state.frames[1]).id,
      photo: { kind: 'upload', photoId: PHOTO, name: 'family.jpg', widthPx: 3000, heightPx: 4000 },
    })
    state = {
      ...state,
      frames: state.frames.map((f, i) => (i === 2 ? { ...f, photo: null } : f)),
      fillWithSamples: true,
    }
    const scene = buildScene(state)
    const quote = buildQuoteDesignData(state, scene, DESIGN_ID)
    const saved = toVersionRequest(state, scene)
    expect(quote.frames.map((f) => f.id)).toEqual(saved.items.map((i) => i.item_id))
    expect(quote.frames.map((f) => f.id)).toEqual(itemIds(state.frames))
    quote.frames.forEach((f, i) => {
      const item = must(saved.items[i])
      expect(f.photo?.kind === 'upload' ? f.photo.photoId : undefined).toBe(item.photo_id)
      expect(f.photo?.kind === 'sample' ? f.photo.sampleId : undefined).toBe(item.sample_id)
      expect(f.sizeId).toBe(item.size_id)
      expect(f.finishId).toBe(item.finish_id)
    })
    expect(quote.frames[1]?.photo).toEqual({ kind: 'upload', photoId: PHOTO, name: 'family.jpg' })
    // "Fill empty frames" samples are quoted too: the quote shows what the customer sees.
    expect(quote.frames[2]?.photo?.kind).toBe('sample')
  })

  it('marks empty frames as none when fill is off, and sends outer positions from the scene', () => {
    let state = createInitialState()
    state = { ...state, frames: state.frames.map((f) => ({ ...f, photo: null })), fillWithSamples: false }
    const scene = buildScene(state)
    const data = buildQuoteDesignData(state, scene, DESIGN_ID)
    expect(data.frames[0]?.photo).toEqual({ kind: 'none' })
    expect(data.frames[0]?.x).toBeCloseTo(must(scene.frames[0]).outer.x, 3)
    expect(data.frames[0]?.y).toBeCloseTo(must(scene.frames[0]).outer.y, 3)
  })

  it('carries a disabled mount and its margin unchanged', () => {
    let state = createInitialState()
    state = plannerReducer(state, {
      type: 'frames/updateMount',
      index: 0,
      patch: { enabled: false, marginIn: 3.5 },
    })
    const data = buildQuoteDesignData(state, buildScene(state), DESIGN_ID)
    expect(data.frames[0]?.mount).toEqual({ enabled: false, colourId: 'museum-white', marginIn: 3.5 })
  })
})

describe('safeWhatsAppUrl', () => {
  it('accepts https links to WhatsApp', () => {
    const url = 'https://wa.me/919800000001?text=Hello%20Moonlight'
    expect(safeWhatsAppUrl(url)).toBe(url)
    expect(safeWhatsAppUrl('https://api.whatsapp.com/send?phone=919800000001')).not.toBeNull()
  })

  it.each([
    'javascript:alert(1)',
    'data:text/html,<script>1</script>',
    'http://wa.me/919800000001',
    'https://evil.example/wa.me/919800000001',
    'https://wa.me.evil.example/x',
    'https://user:pass@wa.me/919800000001',
    'https://wa.me@evil.example/919800000001',
    '//wa.me/919800000001',
    'wa.me/919800000001',
    '',
    null,
    undefined,
    42,
  ])('refuses %j', (value) => {
    expect(safeWhatsAppUrl(value)).toBeNull()
  })

  it('reads the prefilled message and the studio number back', () => {
    const url = 'https://wa.me/919800000001?text=Hello%20%F0%9F%91%8B%0A%0AQuote%20MQ-1'
    expect(whatsAppMessage(url)).toBe('Hello 👋\n\nQuote MQ-1')
    expect(whatsAppNumber(url)).toBe('+919800000001')
    expect(whatsAppNumber('https://wa.me/abc')).toBeNull()
  })
})

describe('safeReportUrl', () => {
  const token = 'LDcWktm_9DuGs9LEC5SGRMBedXLRnZgGj2tq5Zumqp8'
  it('accepts the app’s own /q/<token> link', () => {
    expect(safeReportUrl(`http://localhost:5173/q/${token}`)).toContain(`/q/${token}`)
    expect(safeReportUrl(`/q/${token}`)).toContain(`/q/${token}`)
  })

  it.each([
    'javascript:alert(1)',
    'https://evil.example/q/short',
    '/q/../../etc/passwd',
    '/other/path',
    `/q/${'a'.repeat(200)}`,
    'https://user:pw@localhost/q/LDcWktm_9DuGs9LEC5SGRMBedXLRnZgGj2tq5Zumqp8',
    null,
    7,
  ])('refuses %j', (value) => {
    expect(safeReportUrl(value)).toBeNull()
  })
})

describe('describeQuoteError', () => {
  const e = (status: number, code = 'X', details: { field: string; issue: string }[] = []) =>
    new ApiError({ status, code, message: 'internal server text', details })

  it.each([
    [e(0, 'NETWORK_ERROR'), /offline/, true],
    [e(401), /session ended/, false],
    [e(403), /permission/, false],
    [e(404), /no longer exists/, false],
    [e(409, 'IDEMPOTENCY_KEY_REUSED'), /start the quote request again/, false],
    [e(413), /too large/, true],
    [e(429), /several quotes/, false],
    [e(503), /busy/, true],
    [e(503, 'STORAGE_LIMIT_REACHED'), /storage is full/, false],
    [e(500), /shortly/, true],
    [
      e(422, 'VALIDATION_ERROR', [{ field: 'file', issue: 'Unsupported image signature' }]),
      /preview image/,
      true,
    ],
    [e(422, 'VALIDATION_ERROR', [{ field: 'designId', issue: 'Design differs' }]), /Save it/, false],
    [
      e(422, 'VALIDATION_ERROR', [{ field: 'design_data.wall.widthIn', issue: 'Wall too wide' }]),
      /Wall too wide/,
      false,
    ],
  ])('maps %# to a safe message', (error, message, retryable) => {
    const problem = describeQuoteError(error)
    expect(problem.message).toMatch(message)
    expect(problem.retryable).toBe(retryable)
    expect(problem.message).not.toMatch(/internal server text/)
  })

  it('has a neutral message for unknown failures', () => {
    expect(describeQuoteError(new Error('boom'))).toEqual({
      message: 'We couldn’t prepare your quote request. Please try again.',
      retryable: true,
    })
  })
})

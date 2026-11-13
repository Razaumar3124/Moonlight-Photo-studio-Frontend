import { useCallback, useEffect, useRef, useState, type RefObject } from 'react'
import { quotesService } from '@/services/quotesService'
import { designFingerprint } from '../lib/designMapper'
import { describeSaveError, type DesignSession } from '../lib/designSave'
import { renderWallImage } from '../lib/exportImage'
import type { Scene } from '../lib/geometry/scene'
import type { PlannerState } from '../lib/plannerState'
import {
  buildQuoteDesignData,
  describeQuoteError,
  safeReportUrl,
  safeWhatsAppUrl,
  type QuoteProblem,
} from '../lib/quoteRequest'

export type QuoteStep = 'closed' | 'confirm' | 'saving' | 'preview' | 'sending' | 'ready' | 'error'

export interface QuoteResult {
  quoteId: string
  whatsappUrl: string
  reportUrl: string
}

/**
 * The quote preview is stored for 30 days, so it is kept small: a JPEG about 1600 px wide,
 * aiming under 600 KB. The API accepts at most 2 MB; this ceiling keeps a safe margin.
 */
export const PREVIEW_WIDTH_PX = 1600
export const PREVIEW_TARGET_BYTES = 600 * 1024
export const MAX_PREVIEW_BYTES = 1900 * 1024
const PREVIEW_QUALITIES = [0.85, 0.72, 0.6, 0.48] as const

interface Attempt {
  /** Content the attempt belongs to: any change to the design starts a new one. */
  fingerprint: string
  /** Sent as Idempotency-Key, so a retry of this attempt can never create a second quote. */
  key: string
  preview: Blob | null
  result: QuoteResult | null
}

function newKey(): string {
  const id = globalThis.crypto?.randomUUID?.()
  if (id) return id
  return Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16)).join('')
}

export interface QuoteRequestDeps {
  state: PlannerState
  scene: Scene
  session: DesignSession
  /** True when the planner holds changes that aren't saved (or the design was never saved). */
  needsSave: boolean
  svgRef: RefObject<SVGSVGElement | null>
  /** Save the design if needed (create / new version) and return its session. Throws on failure. */
  ensureSaved: (title: string) => Promise<DesignSession>
}

/**
 * Request a Quote: save the design (if it changed) → render the wall preview → POST
 * /quotes/prepare → hand back the WhatsApp link for the customer to open and send.
 *
 * One attempt per design content: it keeps its idempotency key, its rendered preview and (once it
 * succeeds) its result. So a double click, a retry after a dropped connection, or reopening the
 * dialog never creates a second quote for the same design; changing the design starts a new attempt.
 */
export function useQuoteRequest(deps: QuoteRequestDeps) {
  const [step, setStep] = useState<QuoteStep>('closed')
  const [problem, setProblem] = useState<QuoteProblem | null>(null)
  const [result, setResult] = useState<QuoteResult | null>(null)
  const attempt = useRef<Attempt | null>(null)
  const busy = useRef(false)
  const lastTitle = useRef('')
  // The latest deps, so a retry never works from stale closures.
  const latest = useRef(deps)
  useEffect(() => {
    latest.current = deps
  })

  const open = useCallback(() => {
    const { state, session } = latest.current
    const fp = `${session.designId ?? ''}|${designFingerprint(state)}`
    const done = attempt.current?.fingerprint === fp ? attempt.current.result : null
    setProblem(null)
    setResult(done)
    setStep(done ? 'ready' : 'confirm')
  }, [])

  const close = useCallback(() => {
    if (busy.current) return
    setStep('closed')
  }, [])

  const submit = useCallback(async (title: string) => {
    if (busy.current) return
    busy.current = true
    lastTitle.current = title
    setProblem(null)
    const { state, scene, needsSave, svgRef, ensureSaved, session } = latest.current

    try {
      // 1. Save first: the quote and its report describe the saved design, never unsaved edits.
      let saved = session
      if (needsSave || !session.designId) {
        setStep('saving')
        try {
          saved = await ensureSaved(title)
        } catch (error) {
          const p = describeSaveError(error)
          setProblem({ message: p.message, retryable: !p.fixable })
          setStep('error')
          return
        }
      }
      const designId = saved.designId
      if (!designId) throw new Error('Design was not saved')

      const named = { ...state, title }
      const fingerprint = `${designId}|${designFingerprint(named)}`
      if (attempt.current?.fingerprint !== fingerprint) {
        attempt.current = { fingerprint, key: newKey(), preview: null, result: null }
      }
      const current = attempt.current
      if (current.result) {
        setResult(current.result)
        setStep('ready')
        return
      }

      // 2. The preview image: exactly what is on screen (with dimension guides for the studio).
      if (!current.preview) {
        setStep('preview')
        const svg = svgRef.current
        if (!svg) throw new Error('The wall is not on screen')
        const options = { title, unit: state.displayUnit, guides: true } as const
        let blob: Blob | null = null
        for (const quality of PREVIEW_QUALITIES) {
          blob = await renderWallImage(svg, scene, {
            ...options,
            format: 'image/jpeg',
            width: PREVIEW_WIDTH_PX,
            quality,
          })
          if (blob.size <= PREVIEW_TARGET_BYTES) break
        }
        if (!blob || blob.size > MAX_PREVIEW_BYTES) throw new Error('The preview image is too large')
        current.preview = blob
      }

      // 3. Create the quote (idempotent) and get the WhatsApp link.
      setStep('sending')
      const response = await quotesService.prepare(
        buildQuoteDesignData(named, scene, designId),
        current.preview,
        current.key,
      )
      const whatsappUrl = safeWhatsAppUrl(response.whatsapp_url)
      const reportUrl = safeReportUrl(response.report_url)
      if (!whatsappUrl || !reportUrl) {
        // A response we can't safely use: don't offer links, and let a retry get a clean one.
        setProblem({
          message: 'We couldn’t prepare a safe WhatsApp link. Please try again.',
          retryable: true,
        })
        setStep('error')
        return
      }
      current.result = { quoteId: response.quote_id, whatsappUrl, reportUrl }
      setResult(current.result)
      setStep('ready')
    } catch (error) {
      setProblem(describeQuoteError(error))
      setStep('error')
    } finally {
      busy.current = false
    }
  }, [])

  const retry = useCallback(() => submit(lastTitle.current), [submit])

  /** Start over with a new request key (only offered once a quote exists). */
  const startNew = useCallback(() => {
    attempt.current = null
    setResult(null)
    setProblem(null)
    setStep('confirm')
  }, [])

  return { step, problem, result, open, close, submit, retry, startNew }
}

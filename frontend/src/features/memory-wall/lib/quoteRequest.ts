import { isApiError } from '@/services/apiClient'
import type { QuoteDesignData } from '@/types/api'
import { itemIds, shownPhoto } from './designMapper'
import type { Scene } from './geometry/scene'
import type { PlannerState } from './plannerState'

/**
 * Request a Quote: building the payload, trusting the link we are given, and explaining failures.
 * There is no pricing here: the studio prices every design on WhatsApp.
 */

/** The planner state → `design_data` of POST /quotes/prepare (frame ids and photos match the saved design). */
export function buildQuoteDesignData(state: PlannerState, scene: Scene, designId: string): QuoteDesignData {
  const ids = itemIds(state.frames)
  return {
    title: state.title,
    designId,
    displayUnit: state.displayUnit,
    preview: { sofa: state.preview.sofa },
    wall: { widthIn: state.wall.widthIn, heightIn: state.wall.heightIn, paintId: state.wall.paintId },
    layout: { style: state.layout.style, gapIn: state.layout.gapIn },
    frames: state.frames.map((frame, i) => {
      const photo = shownPhoto(frame, i, state.fillWithSamples)
      const placed = scene.frames[i]
      return {
        id: ids[i] as string,
        sizeId: frame.sizeId,
        orientation: frame.orientation,
        finishId: frame.finishId,
        mount: {
          enabled: frame.mount.enabled,
          colourId: frame.mount.colourId,
          marginIn: frame.mount.marginIn,
        },
        photo:
          photo?.kind === 'upload'
            ? { kind: 'upload', photoId: photo.photoId, name: photo.name }
            : photo?.kind === 'sample'
              ? { kind: 'sample', sampleId: photo.sampleId }
              : { kind: 'none' },
        x: Math.max(0, Math.round((placed?.outer.x ?? 0) * 10000) / 10000),
        y: Math.max(0, Math.round((placed?.outer.y ?? 0) * 10000) / 10000),
      }
    }),
  }
}

/** The WhatsApp hosts a prepared link may point to. Anything else is never opened. */
const WHATSAPP_HOSTS = new Set(['wa.me', 'api.whatsapp.com', 'web.whatsapp.com'])

/**
 * The API hands back a ready-made link, but it is still a URL we are about to put in an `href`:
 * accept only https links to WhatsApp, never `javascript:`, `data:` or another site.
 */
export function safeWhatsAppUrl(url: unknown): string | null {
  if (typeof url !== 'string' || url.length > 4000) return null
  try {
    const parsed = new URL(url)
    if (parsed.protocol !== 'https:' || parsed.username || parsed.password) return null
    return WHATSAPP_HOSTS.has(parsed.hostname) ? parsed.href : null
  } catch {
    return null
  }
}

/** The prefilled message inside a WhatsApp link, for the "Copy message" fallback. */
export function whatsAppMessage(url: string): string | null {
  try {
    return new URL(url).searchParams.get('text')
  } catch {
    return null
  }
}

/** The studio's number from a WhatsApp link (`https://wa.me/919800000001?text=…` → `+919800000001`). */
export function whatsAppNumber(url: string): string | null {
  try {
    const digits = new URL(url).pathname.replace(/\D/g, '')
    return /^\d{10,15}$/.test(digits) ? `+${digits}` : null
  } catch {
    return null
  }
}

/** The share link must stay on our own app origin (`/q/<token>`), never an arbitrary site. */
export function safeReportUrl(url: unknown): string | null {
  if (typeof url !== 'string') return null
  try {
    const parsed = new URL(url, window.location.origin)
    if (!/^https?:$/.test(parsed.protocol) || parsed.username || parsed.password) return null
    return /^\/q\/[A-Za-z0-9_-]{16,128}$/.test(parsed.pathname) ? parsed.href : null
  } catch {
    return null
  }
}

export interface QuoteProblem {
  message: string
  /** Retrying (with the same request key) can help. */
  retryable: boolean
}

export function describeQuoteError(error: unknown): QuoteProblem {
  if (!isApiError(error)) {
    return { message: 'We couldn’t prepare your quote request. Please try again.', retryable: true }
  }
  if (error.isNetworkError) {
    return {
      message: 'You appear to be offline. Your design is kept here: try again when you’re back.',
      retryable: true,
    }
  }
  switch (error.status) {
    case 401:
      return {
        message: 'Your session ended. Sign in again and your design will still be here.',
        retryable: false,
      }
    case 403:
      return {
        message: 'You don’t have permission to use one of the photos or the design.',
        retryable: false,
      }
    case 404:
      return {
        message: 'That design no longer exists. Save it again, then request the quote.',
        retryable: false,
      }
    case 409:
      return {
        message: 'This request was already used. Please start the quote request again.',
        retryable: false,
      }
    case 413:
      return { message: 'The preview image is too large. Please try again.', retryable: true }
    case 422:
    case 400: {
      const first = error.details[0]
      const onPreview = first?.field === 'file'
      return {
        message: onPreview
          ? 'We couldn’t use the preview image. Please try again.'
          : first?.field === 'designId'
            ? 'Your design changed since it was saved. Save it, then request the quote.'
            : `The quote can’t be prepared yet: ${first?.issue ?? error.message}`,
        retryable: onPreview,
      }
    }
    case 429:
      return {
        message: 'You’ve requested several quotes recently. Please wait a little before another one.',
        retryable: false,
      }
    case 503:
      return { message: 'The service is busy right now. Please try again shortly.', retryable: true }
    default:
      return {
        message: 'We couldn’t prepare your quote request. Please try again shortly.',
        retryable: error.status >= 500,
      }
  }
}

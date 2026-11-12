/**
 * Contract §8 — WhatsApp quote requests and the shared design report.
 * There is no online pricing: the studio prices each design on WhatsApp.
 */
import type { EntityId, ISODateTime } from './common'
import type { DisplayUnit, LayoutType } from './designs'

/* ----------------------------- §8.1 Prepare -------------------------------- */

/**
 * `design_data` for POST /quotes/prepare: the planner's own state (camelCase), JSON-encoded in
 * a multipart form next to the rendered preview (`file`: PNG, WebP or JPEG, ≤ 15 MB).
 * Catalog IDs are validated; unknown sizes, finishes, mounts or paints are rejected (422).
 */
export interface QuoteDesignData {
  /** ≤ 100 characters. */
  title?: string
  designId?: EntityId | null
  displayUnit?: DisplayUnit
  preview?: { sofa?: boolean }
  wall: {
    /** 36–480 */
    widthIn: number
    /** 48–240 */
    heightIn: number
    paintId?: string | null
  }
  layout?: { style?: LayoutType; gapIn?: number }
  /** 1–16 frames. */
  frames: Array<{
    id: string
    sizeId: string
    orientation?: 'portrait' | 'landscape'
    finishId: string
    mount?: { enabled?: boolean; colourId?: string | null; marginIn?: number }
    /** Uploads must reference a photo the user uploaded (`photoId`). */
    photo?: {
      kind: 'sample' | 'upload' | 'none'
      sampleId?: string
      photoId?: EntityId
      name?: string
    } | null
  }>
}

export type QuoteStatus = 'draft' | 'pending_review' | 'contacted' | 'converted' | 'expired' | (string & {})

/** 201 from POST /quotes/prepare (bearer auth; rate-limited per user). */
export interface QuotePrepareResponse {
  /** Reference, e.g. `MQ-2026-0012`. Use it with GET /quotes/{id}. */
  quote_id: string
  status: QuoteStatus
  /** Open in a new tab: WhatsApp with the prefilled quote message. */
  whatsapp_url: string
  /** Public share link. Returned **only here**; the server keeps just a hash of its token. */
  report_url: string
  expires_at: ISODateTime
}

/* ---------------------------- §8.2 Read back ------------------------------- */

/** One row of the report's frame table (display strings). */
export interface QuoteFrameSummary {
  number: number
  /** Photo opening as hung, e.g. `16 × 12 in`. */
  size: string
  /** Outer size, e.g. `22 × 18 in`. */
  dimensions: string
  orientation: string
  finish: string
  /** e.g. `Museum White (2 in border)` or `No mount`. */
  mount: string
  photo: string | null
}

/** GET /quotes/{id} — owner only (404 otherwise). */
export interface QuoteDetail {
  quote_id: string
  status: QuoteStatus
  design_title: string
  layout_style: string
  /** In the customer's unit, e.g. `12 × 9 ft`. */
  wall_size: string
  frame_count: number
  finish_summary: string
  /** Always null: see QuotePrepareResponse.report_url. */
  report_url: null
  /** Short-lived signed URL of the preview image. */
  preview_url: string
  customer_name: string
  customer_phone: string | null
  customer_email: string
  frames: QuoteFrameSummary[]
  expires_at: ISODateTime
  created_at: ISODateTime
}

/** GET /quotes/share/{token} with `Accept: application/json` (HTML report otherwise). */
export interface QuoteShare {
  quote_id: string
  created_at: ISODateTime
  expires_at: ISODateTime
  customer_name: string
  customer_contact_masked: string
  design_title: string
  layout_style: string
  wall_dimensions: string
  frame_count: number
  finish_summary: string
  preview_image_url: string
  frames: QuoteFrameSummary[]
}

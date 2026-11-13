import type { QuoteDesignData, QuotePrepareResponse } from '@/types/api'
import { api } from './apiClient'
import { endpoints } from './endpoints'

const PREVIEW_EXTENSIONS: Record<string, string> = {
  'image/jpeg': 'jpg',
  'image/webp': 'webp',
  'image/png': 'png',
}

export const quotesService = {
  /**
   * POST /quotes/prepare (multipart: `file` = the wall preview, `design_data` = JSON).
   * `idempotencyKey` makes a retry or double click return the same quote instead of a new one.
   */
  prepare: (designData: QuoteDesignData, preview: Blob, idempotencyKey: string, signal?: AbortSignal) => {
    const form = new FormData()
    form.append('design_data', JSON.stringify(designData))
    form.append('file', preview, `wall-preview.${PREVIEW_EXTENSIONS[preview.type] ?? 'jpg'}`)
    return api.post<QuotePrepareResponse>(endpoints.quotes.prepare, form, {
      headers: { 'Idempotency-Key': idempotencyKey },
      signal,
    })
  },
}

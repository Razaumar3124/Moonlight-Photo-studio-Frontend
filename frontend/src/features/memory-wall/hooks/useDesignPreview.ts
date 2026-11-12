import { useEffect, useMemo, useState } from 'react'
import { designsService } from '@/services/designsService'
import type { DesignDetail } from '@/types/api'
import { fromDesignDetail, type LoadedDesign } from '../lib/designMapper'
import { usePhotos } from './usePhotoLibrary'

/**
 * "My Designs" cards draw a live preview, which needs each design's items: one GET /designs/{id}
 * per card. They are fetched a few at a time and cached by version, so opening the dialog again
 * (or scrolling) doesn't refetch, and a new version naturally gets a new key.
 */
const MAX_PARALLEL = 3
const cache = new Map<string, DesignDetail>()
const queue: Array<() => void> = []
let running = 0

function schedule<T>(task: () => Promise<T>): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const start = () => {
      running += 1
      task()
        .then(resolve, reject)
        .finally(() => {
          running -= 1
          queue.shift()?.()
        })
    }
    if (running < MAX_PARALLEL) start()
    else queue.push(start)
  })
}

export type PreviewStatus = 'loading' | 'ready' | 'empty' | 'error'

export function useDesignPreview(designId: string, versionKey: string | null) {
  const library = usePhotos()
  const key = `${designId}@${versionKey ?? 'none'}`
  // Results are tagged with the key they answer, so a new version never shows the old preview.
  const [fetched, setFetched] = useState<{ key: string; detail: DesignDetail } | null>(null)
  const [failedKey, setFailedKey] = useState<string | null>(null)
  const detail = cache.get(key) ?? (fetched?.key === key ? fetched.detail : null)

  useEffect(() => {
    if (cache.has(key)) return
    let cancelled = false
    schedule(() => designsService.detail(designId))
      .then((res) => {
        cache.set(key, res)
        if (!cancelled) setFetched({ key, detail: res })
      })
      .catch(() => {
        if (!cancelled) setFailedKey(key)
      })
    return () => {
      cancelled = true
    }
  }, [designId, key])

  const failed = failedKey === key && !detail
  const photos = useMemo(() => new Map(library.photos.map((p) => [p.id, p])), [library.photos])
  const loaded: LoadedDesign | null = useMemo(
    () => (detail ? fromDesignDetail(detail, photos) : null),
    [detail, photos],
  )
  const status: PreviewStatus = failed ? 'error' : !detail ? 'loading' : loaded ? 'ready' : 'empty'
  return { status, loaded }
}

/** Forget cached previews (after a design was deleted or saved elsewhere). */
export function forgetDesignPreview(designId: string) {
  for (const key of cache.keys()) if (key.startsWith(`${designId}@`)) cache.delete(key)
}

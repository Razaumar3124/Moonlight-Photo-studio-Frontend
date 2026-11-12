import { useCallback, useEffect, useRef, useState } from 'react'
import { isApiError } from '@/services/apiClient'
import { designsService } from '@/services/designsService'
import type { DesignListItem } from '@/types/api'

export type DesignListStatus = 'idle' | 'loading' | 'ready' | 'error'

const PAGE_SIZE = 12
const SEARCH_DEBOUNCE_MS = 300

export interface DesignList {
  status: DesignListStatus
  items: readonly DesignListItem[]
  total: number
  hasMore: boolean
  loadingMore: boolean
  search: string
  setSearch: (value: string) => void
  loadMore: () => void
  reload: () => void
  remove: (designId: string) => Promise<{ ok: true } | { ok: false; error: string }>
}

interface Loaded {
  /** Which request (search term + reload counter) these results belong to. */
  key: string
  items: readonly DesignListItem[]
  total: number
  page: number
}

/**
 * "My Designs" from GET /designs: server-side search and paging, newest first. Only loads while
 * `enabled` (the dialog is open). Results are tagged with the request they answer, so a slow
 * response to an old search can never be shown as the current one (and superseded requests are
 * aborted).
 */
export function useDesignList(enabled: boolean): DesignList {
  const [search, setSearch] = useState('')
  const [debounced, setDebounced] = useState('')
  const [reloadTick, setReloadTick] = useState(0)
  const [loaded, setLoaded] = useState<Loaded | null>(null)
  const [failedKey, setFailedKey] = useState<string | null>(null)
  const [loadingMore, setLoadingMore] = useState(false)
  const loadingMoreRef = useRef(false)

  const requestKey = enabled ? `${debounced}\u0000${reloadTick}` : null

  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(search.trim()), SEARCH_DEBOUNCE_MS)
    return () => window.clearTimeout(timer)
  }, [search])

  useEffect(() => {
    if (!requestKey) return
    const controller = new AbortController()
    designsService
      .list({ page: 1, page_size: PAGE_SIZE, search: debounced || undefined }, controller.signal)
      .then((res) => setLoaded({ key: requestKey, items: res.items, total: res.total, page: 1 }))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setFailedKey(requestKey)
      })
    return () => controller.abort()
  }, [requestKey, debounced])

  const current = loaded && loaded.key === requestKey ? loaded : null
  const status: DesignListStatus = !requestKey
    ? 'idle'
    : current
      ? 'ready'
      : failedKey === requestKey
        ? 'error'
        : 'loading'
  // While a new search is loading, keep showing the previous results rather than a blank flash.
  const shown = current ?? loaded
  const items = shown?.items ?? []
  const total = shown?.total ?? 0

  const loadMore = useCallback(() => {
    if (loadingMoreRef.current || !current || !requestKey) return
    loadingMoreRef.current = true
    setLoadingMore(true)
    const next = current.page + 1
    designsService
      .list({ page: next, page_size: PAGE_SIZE, search: debounced || undefined })
      .then((res) =>
        setLoaded((now) => {
          if (!now || now.key !== requestKey) return now
          const known = new Set(now.items.map((d) => d.id))
          return {
            ...now,
            items: [...now.items, ...res.items.filter((d) => !known.has(d.id))],
            total: res.total,
            page: next,
          }
        }),
      )
      .catch(() => setFailedKey(requestKey))
      .finally(() => {
        loadingMoreRef.current = false
        setLoadingMore(false)
      })
  }, [current, requestKey, debounced])

  const remove = useCallback(async (designId: string) => {
    try {
      await designsService.remove(designId)
    } catch (error) {
      // Already gone (another tab): the list should agree.
      if (!(isApiError(error) && error.status === 404)) {
        return {
          ok: false as const,
          error:
            isApiError(error) && error.isNetworkError
              ? 'You appear to be offline. Check your connection and try again.'
              : 'We couldn’t delete that design. Please try again.',
        }
      }
    }
    setLoaded((now) =>
      now
        ? { ...now, items: now.items.filter((d) => d.id !== designId), total: Math.max(0, now.total - 1) }
        : now,
    )
    return { ok: true as const }
  }, [])

  return {
    status,
    items,
    total,
    hasMore: items.length < total,
    loadingMore,
    search,
    setSearch,
    loadMore,
    reload: () => {
      setFailedKey(null)
      setReloadTick((n) => n + 1)
    },
    remove,
  }
}

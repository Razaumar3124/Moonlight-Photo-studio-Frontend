import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { isApiError } from '@/services/apiClient'
import { photosService } from '@/services/photosService'
import type { PhotoRef } from '../lib/plannerState'
import { formatBytes, preparePhotoForUpload } from '../lib/photoCompress'
import {
  checkPhotoFile,
  PHOTO_TOO_LARGE_MESSAGE,
  STORAGE_FULL_MESSAGE,
  toLibraryPhoto,
  toPhotoRef,
  URL_REFRESH_MARGIN_MS,
  type LibraryPhoto,
} from '../lib/photos'

export type LibraryStatus = 'loading' | 'ready' | 'error'

export type UploadResult =
  | {
      ok: true
      photo: Extract<PhotoRef, { kind: 'upload' }>
      reused: boolean
      /** Set when the photo was shrunk to fit the 2 MB limit, e.g. "Your photo was 4.1 MB…". */
      notice?: string
    }
  | { ok: false; error: string }

export type RemoveResult = { ok: true } | { ok: false; error: string; inUse: boolean }

export interface UploadHandlers {
  /** 0–1 of the file sent. */
  onProgress?: (fraction: number) => void
}

export interface PhotoLibrary {
  status: LibraryStatus
  /** Newest first. */
  photos: readonly LibraryPhoto[]
  /** The photo's current signed preview URL, or undefined if it isn't in the library. */
  urlFor: (photoId: string) => string | undefined
  has: (photoId: string) => boolean
  upload: (file: File, handlers?: UploadHandlers) => Promise<UploadResult>
  remove: (photoId: string) => Promise<RemoveResult>
  /** Fetch the list again (fresh signed URLs, photos added elsewhere). */
  refresh: () => Promise<void>
  /** An `<img>` failed to load (e.g. an expired signature): refresh, at most once in a while. */
  reportBroken: () => void
}

const CHECK_EVERY_MS = 60 * 1000
const BROKEN_REFRESH_COOLDOWN_MS = 15 * 1000
/** Per-session duplicate detection key. */
const fingerprint = (file: File) => `${file.name}\u0000${file.size}\u0000${file.lastModified}`

function uploadErrorMessage(error: unknown): string {
  if (!isApiError(error)) return 'We couldn’t upload that photo. Please try again.'
  if (error.isNetworkError) return 'You appear to be offline. Check your connection and try again.'
  if (error.status === 429) return 'You’ve uploaded a lot of photos. Please wait a little before adding more.'
  if (error.status === 413) return PHOTO_TOO_LARGE_MESSAGE
  if (error.code === 'STORAGE_LIMIT_REACHED') return STORAGE_FULL_MESSAGE
  if (error.status === 422 || error.status === 400) {
    // The API's own wording for file problems is user-safe (size, format, pixel limits).
    return error.details[0]?.issue || error.message || 'That photo can’t be used. Please choose another.'
  }
  if (error.status === 503) return 'Photo storage is unavailable right now. Please try again shortly.'
  return 'We couldn’t upload that photo. Please try again.'
}

/**
 * The user's photo library (GET /photos) for the planner page: upload with progress, delete,
 * and signed-URL freshness. Owned by the page so photos outlive panels, layout switches and Undo.
 */
export function usePhotoLibrary(): PhotoLibrary {
  const [status, setStatus] = useState<LibraryStatus>('loading')
  const [photos, setPhotos] = useState<readonly LibraryPhoto[]>([])
  const photosRef = useRef(photos)
  /** Ids known to exist, updated synchronously (state lags a render behind, which matters for dedupe). */
  const knownIds = useRef(new Set<string>())
  const sessionUploads = useRef(new Map<string, Promise<UploadResult>>())
  const refreshing = useRef<Promise<void> | null>(null)
  const refreshId = useRef<symbol | null>(null)
  const lastBroken = useRef(0)
  const mounted = useRef(true)
  const abort = useRef(new AbortController())

  useEffect(() => {
    photosRef.current = photos
  }, [photos])

  const refresh = useCallback((): Promise<void> => {
    if (refreshing.current) return refreshing.current
    const signal = abort.current.signal
    const id = Symbol('refresh')
    refreshId.current = id
    const task: Promise<void> = (async () => {
      try {
        const list = await photosService.listAll(signal)
        if (!mounted.current || signal.aborted) return
        const now = Date.now()
        knownIds.current = new Set(list.map((p) => p.id))
        setPhotos(list.map((p) => toLibraryPhoto(p, now)))
        setStatus('ready')
      } catch (error) {
        if (error instanceof DOMException && error.name === 'AbortError') return
        // Keep what we have: stale URLs may still work, and the list is only a convenience.
        if (mounted.current) setStatus((s) => (s === 'ready' ? 'ready' : 'error'))
      } finally {
        if (refreshId.current === id) refreshing.current = null
      }
    })()
    refreshing.current = task
    return task
  }, [])

  // Load, then keep URLs fresh: periodic check, and again when the tab returns or comes online.
  useEffect(() => {
    mounted.current = true
    abort.current = new AbortController()
    void refresh()
    const soon = () => {
      const list = photosRef.current
      if (list.length && Math.min(...list.map((p) => p.expiresAt)) - Date.now() < URL_REFRESH_MARGIN_MS) {
        void refresh()
      }
    }
    const timer = window.setInterval(soon, CHECK_EVERY_MS)
    const onVisible = () => {
      if (document.visibilityState === 'visible') soon()
    }
    const onOnline = () => void refresh()
    document.addEventListener('visibilitychange', onVisible)
    window.addEventListener('online', onOnline)
    const controller = abort.current
    return () => {
      mounted.current = false
      controller.abort()
      // The request tied to this controller is dead: a remount (StrictMode) must start its own.
      refreshing.current = null
      refreshId.current = null
      window.clearInterval(timer)
      document.removeEventListener('visibilitychange', onVisible)
      window.removeEventListener('online', onOnline)
    }
  }, [refresh])

  const byId = useMemo(() => new Map(photos.map((p) => [p.id, p])), [photos])
  const urlFor = useCallback((photoId: string) => byId.get(photoId)?.previewUrl || undefined, [byId])
  const has = useCallback((photoId: string) => byId.has(photoId), [byId])

  const upload = useCallback((file: File, handlers?: UploadHandlers): Promise<UploadResult> => {
    const key = fingerprint(file)
    // The same file chosen twice (double click, drop + pick) is one upload; if it already
    // finished and the photo is still in the library, it is reused instead of stored again.
    const existing = sessionUploads.current.get(key)
    if (existing) {
      return existing.then((result) =>
        result.ok && knownIds.current.has(result.photo.photoId) ? { ...result, reused: true } : run(),
      )
    }
    return run()

    function run(): Promise<UploadResult> {
      const task = (async (): Promise<UploadResult> => {
        const problem = checkPhotoFile(file)
        if (problem) return { ok: false, error: problem }
        // Under the 2 MB limit and a sensible size: sent as is. Otherwise shrunk right here.
        const prepared = await preparePhotoForUpload(file)
        if (!prepared.ok) return { ok: false, error: prepared.error }
        try {
          const photo = await photosService.upload(prepared.photo.file, {
            onProgress: handlers?.onProgress,
            signal: abort.current.signal,
          })
          const summary = toLibraryPhoto({ ...photo }, Date.now())
          knownIds.current.add(summary.id)
          if (mounted.current) {
            setPhotos((list) => [summary, ...list.filter((p) => p.id !== summary.id)])
            setStatus('ready')
          }
          const { optimized, originalBytes, file: sent } = prepared.photo
          return {
            ok: true,
            photo: toPhotoRef(summary),
            reused: false,
            notice: optimized
              ? `Your photo was ${formatBytes(originalBytes)}, so we optimised it to ${formatBytes(sent.size)}.`
              : undefined,
          }
        } catch (error) {
          if (error instanceof DOMException && error.name === 'AbortError') {
            return { ok: false, error: 'Upload cancelled.' }
          }
          return { ok: false, error: uploadErrorMessage(error) }
        }
      })()
      sessionUploads.current.set(key, task)
      // A failed attempt must not block retrying the same file.
      void task.then((r) => {
        if (!r.ok && sessionUploads.current.get(key) === task) sessionUploads.current.delete(key)
      })
      return task
    }
  }, [])

  const remove = useCallback(async (photoId: string): Promise<RemoveResult> => {
    try {
      await photosService.remove(photoId)
      knownIds.current.delete(photoId)
      if (mounted.current) setPhotos((list) => list.filter((p) => p.id !== photoId))
      for (const [key, task] of sessionUploads.current) {
        void task.then((r) => {
          if (r.ok && r.photo.photoId === photoId) sessionUploads.current.delete(key)
        })
      }
      return { ok: true }
    } catch (error) {
      if (isApiError(error) && error.code === 'PHOTO_IN_USE') {
        return { ok: false, inUse: true, error: error.message }
      }
      if (isApiError(error) && error.status === 404) {
        // Already gone (another tab): the list should agree.
        knownIds.current.delete(photoId)
        if (mounted.current) setPhotos((list) => list.filter((p) => p.id !== photoId))
        return { ok: true }
      }
      return {
        ok: false,
        inUse: false,
        error:
          isApiError(error) && error.isNetworkError
            ? 'You appear to be offline. Check your connection and try again.'
            : 'We couldn’t delete that photo. Please try again.',
      }
    }
  }, [])

  const reportBroken = useCallback(() => {
    const now = Date.now()
    if (now - lastBroken.current < BROKEN_REFRESH_COOLDOWN_MS) return
    lastBroken.current = now
    void refresh()
  }, [refresh])

  return useMemo(
    () => ({ status, photos, urlFor, has, upload, remove, refresh, reportBroken }),
    [status, photos, urlFor, has, upload, remove, refresh, reportBroken],
  )
}

/** Provided by the planner page; panels read it instead of threading props through every layout. */
export const PhotoLibraryContext = createContext<PhotoLibrary | null>(null)

export function usePhotos(): PhotoLibrary {
  const ctx = useContext(PhotoLibraryContext)
  if (!ctx) throw new Error('usePhotos must be used inside the planner page')
  return ctx
}

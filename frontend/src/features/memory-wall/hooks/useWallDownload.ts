import { useCallback, useEffect, useRef, useState, type RefObject } from 'react'
import { downloadWallPng } from '../lib/exportImage'
import type { Scene } from '../lib/geometry/scene'
import type { PlannerState } from '../lib/plannerState'

export type DownloadStatus = 'idle' | 'busy' | 'done' | 'error'

export const DOWNLOAD_MESSAGE: Record<DownloadStatus, string> = {
  idle: '',
  busy: 'Preparing your image…',
  done: 'Your wall design was downloaded as a PNG.',
  error: 'We couldn’t create the image. Please try again.',
}

/**
 * "Download as PNG" for a rendered wall. `done` falls back to `idle` after a moment;
 * `error` stays until the next attempt. Resolves with the final status for callers that
 * report it elsewhere (a toast).
 */
export function useWallDownload(
  svgRef: RefObject<SVGSVGElement | null>,
  scene: Scene,
  state: Pick<PlannerState, 'title' | 'displayUnit' | 'preview'>,
) {
  const [status, setStatus] = useState<DownloadStatus>('idle')
  const busy = useRef(false)
  const timer = useRef<number | undefined>(undefined)
  useEffect(() => () => window.clearTimeout(timer.current), [])

  const { title, displayUnit } = state
  const guides = state.preview.guides
  const download = useCallback(async (): Promise<DownloadStatus> => {
    const svg = svgRef.current
    if (!svg || busy.current) return 'idle'
    busy.current = true
    window.clearTimeout(timer.current)
    setStatus('busy')
    try {
      await downloadWallPng(svg, scene, { title, unit: displayUnit, guides })
      setStatus('done')
      timer.current = window.setTimeout(() => setStatus('idle'), 2200)
      return 'done'
    } catch {
      setStatus('error')
      return 'error'
    } finally {
      busy.current = false
    }
  }, [svgRef, scene, title, displayUnit, guides])

  return { status, download }
}

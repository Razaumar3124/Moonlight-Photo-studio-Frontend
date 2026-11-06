import { useEffect } from 'react'

/**
 * Adds `viewport-fit=cover` to the viewport meta while the calling page is mounted, so the auth
 * pages can paint edge to edge on notched phones and pad their content with
 * `env(safe-area-inset-*)`. It is scoped instead of being set in index.html because other pages
 * (the planner) don't pad for safe areas yet. The original value is restored on unmount.
 */
export function useViewportFitCover() {
  useEffect(() => {
    const meta = document.querySelector<HTMLMetaElement>('meta[name="viewport"]')
    if (!meta || meta.content.includes('viewport-fit')) return

    const original = meta.content
    meta.content = `${original}, viewport-fit=cover`
    return () => {
      meta.content = original
    }
  }, [])
}

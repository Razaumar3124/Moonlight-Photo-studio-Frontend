import { useCallback, useMemo, useSyncExternalStore } from 'react'

/**
 * Live `matchMedia` result. Use it only when something must not *mount* at all (e.g. to skip
 * downloading an image). For purely visual changes use Tailwind variants instead.
 */
export function useMediaQuery(query: string): boolean {
  // One MediaQueryList per query: getSnapshot runs on every render and must be cheap.
  const mql = useMemo(() => window.matchMedia(query), [query])

  const subscribe = useCallback(
    (onChange: () => void) => {
      mql.addEventListener('change', onChange)
      return () => mql.removeEventListener('change', onChange)
    },
    [mql],
  )

  return useSyncExternalStore(
    subscribe,
    () => mql.matches,
    () => false,
  )
}

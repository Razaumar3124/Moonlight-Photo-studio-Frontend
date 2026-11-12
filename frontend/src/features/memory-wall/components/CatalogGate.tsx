import { useEffect, useState, type ReactNode } from 'react'
import { PageLoader } from '@/components/layout/PageLoader'
import { useToast } from '@/components/feedback/toastContext'
import { loadCatalog } from '../lib/catalog'

/**
 * Holds the planner back until the backend catalog (options, rules, templates) has been loaded
 * and installed, so the first render already uses the source of truth. If the catalog can't be
 * fetched or fails validation, the planner opens with its bundled defaults (contract-tested to
 * match) and says so once.
 */
export function CatalogGate({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false)
  const toast = useToast()

  useEffect(() => {
    let cancelled = false
    void loadCatalog().then((result) => {
      if (cancelled) return
      setReady(true)
      if (result.source === 'bundled') {
        toast({
          tone: 'info',
          message: 'Couldn’t refresh the latest frame options, so the built-in ones are shown.',
          action: { label: 'Reload', onClick: () => window.location.reload() },
          duration: 0,
        })
      }
    })
    return () => {
      cancelled = true
    }
  }, [toast])

  return ready ? children : <PageLoader />
}

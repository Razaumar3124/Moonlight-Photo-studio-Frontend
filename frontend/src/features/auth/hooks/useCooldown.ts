import { useCallback, useEffect, useState } from 'react'

/**
 * Whole seconds left on a cooldown (e.g. before another code may be requested). `start(seconds)`
 * (re)starts it. Counts down against the clock rather than by decrementing, so a throttled
 * background tab shows the right value when it wakes.
 */
export function useCooldown() {
  const [endsAt, setEndsAt] = useState(0)
  const [remaining, setRemaining] = useState(0)

  useEffect(() => {
    const tick = () => setRemaining(Math.max(0, Math.ceil((endsAt - Date.now()) / 1000)))
    tick()
    if (endsAt <= Date.now()) return
    const timer = setInterval(() => {
      tick()
      if (Date.now() >= endsAt) clearInterval(timer)
    }, 500)
    return () => clearInterval(timer)
  }, [endsAt])

  const start = useCallback((seconds: number) => {
    const safe = Number.isFinite(seconds) && seconds > 0 ? Math.min(seconds, 600) : 60
    setEndsAt(Date.now() + safe * 1000)
  }, [])

  return { remaining, start }
}

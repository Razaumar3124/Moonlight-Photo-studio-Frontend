import { useEffect, type RefObject } from 'react'

/**
 * Closes a non-modal popup (menu, popover) on a pointer press outside `rootRef`.
 * Escape and focus handling stay with the component, which knows where focus should return.
 */
export function useDismiss(rootRef: RefObject<HTMLElement | null>, open: boolean, onDismiss: () => void) {
  useEffect(() => {
    if (!open) return
    const onDown = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) onDismiss()
    }
    document.addEventListener('pointerdown', onDown)
    return () => document.removeEventListener('pointerdown', onDown)
  }, [open, onDismiss, rootRef])
}

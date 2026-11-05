import { createContext, useContext, type ReactNode } from 'react'

export type ToastTone = 'success' | 'info' | 'error'

export interface ToastInput {
  tone?: ToastTone
  message: ReactNode
  action?: { label: string; onClick: () => void }
  /** ms; 0 keeps it until dismissed. Default 5000 (8000 with an action). Pauses on hover/focus. */
  duration?: number
}

export const ToastContext = createContext<((toast: ToastInput) => void) | null>(null)

/** Show a toast: `toast({ tone: 'success', message: 'Saved', action: { label: 'Undo', onClick } })`. */
export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>')
  return ctx
}

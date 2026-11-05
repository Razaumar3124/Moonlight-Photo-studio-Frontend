import { CircleAlert, CircleCheck, Info, X, type LucideIcon } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { cn } from '@/lib/cn'

import { ToastContext, type ToastInput, type ToastTone } from './toastContext'

interface Toast extends ToastInput {
  id: number
}

const icons: Record<ToastTone, LucideIcon> = { success: CircleCheck, info: Info, error: CircleAlert }
const iconTone: Record<ToastTone, string> = {
  success: 'text-success-500',
  info: 'text-gold-500',
  error: 'text-danger-600',
}

/** Toasts with an action (e.g. Undo) stay longer: there's something to do, not just read. */
const DEFAULT_MS = 5000
const ACTION_MS = 8000

/**
 * Lightweight toasts: polite live region, newest at the bottom, max 3, auto-dismiss.
 * Positioned above the mobile action bar.
 */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const nextId = useRef(1)

  const dismiss = useCallback((id: number) => setToasts((list) => list.filter((t) => t.id !== id)), [])

  const show = useCallback((input: ToastInput) => {
    const id = nextId.current++
    setToasts((list) => [...list.slice(-2), { ...input, id }])
  }, [])

  const value = useMemo(() => show, [show])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        role="status"
        aria-live="polite"
        className="pointer-events-none fixed inset-x-0 bottom-24 z-[60] flex flex-col items-center gap-2 px-4 md:bottom-6"
      >
        {toasts.map((t) => (
          <ToastItem key={t.id} toast={t} onDismiss={() => dismiss(t.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  )
}

/**
 * One toast. The auto-dismiss timer pauses while it's hovered or has keyboard focus (WCAG 2.2.1),
 * so nobody loses an Undo while reaching for it.
 */
function ToastItem({ toast: t, onDismiss }: { toast: Toast; onDismiss: () => void }) {
  const [paused, setPaused] = useState(false)
  const remaining = useRef(t.duration ?? (t.action ? ACTION_MS : DEFAULT_MS))
  const onDismissRef = useRef(onDismiss)
  useEffect(() => {
    onDismissRef.current = onDismiss
  })

  useEffect(() => {
    if (paused || remaining.current <= 0) return
    const started = Date.now()
    const timer = window.setTimeout(() => onDismissRef.current(), remaining.current)
    return () => {
      window.clearTimeout(timer)
      remaining.current -= Date.now() - started
    }
  }, [paused])

  const tone = t.tone ?? 'info'
  const Icon = icons[tone]
  return (
    <div
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={(e) => {
        if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setPaused(false)
      }}
      className="pointer-events-auto flex w-full max-w-md animate-[toast-in_220ms_cubic-bezier(0.2,0.9,0.3,1)] items-center gap-3 rounded-xl border border-cream-300 bg-ink-900 py-2.5 pr-2 pl-3.5 text-sm text-cream-50 shadow-2xl"
    >
      <Icon aria-hidden className={cn('size-5 shrink-0', iconTone[tone])} />
      <div className="min-w-0 flex-1">{t.message}</div>
      {t.action && (
        <button
          type="button"
          onClick={() => {
            t.action?.onClick()
            onDismiss()
          }}
          className="shrink-0 rounded-md px-2.5 py-1.5 font-semibold text-gold-300 hover:bg-white/10"
        >
          {t.action.label}
        </button>
      )}
      <button
        type="button"
        aria-label="Dismiss notification"
        onClick={onDismiss}
        className="grid size-8 shrink-0 place-items-center rounded-md text-cream-300 hover:bg-white/10"
      >
        <X aria-hidden className="size-4" />
      </button>
    </div>
  )
}

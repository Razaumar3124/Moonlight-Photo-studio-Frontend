import { CircleAlert, CircleCheck, Sofa, Sparkles } from 'lucide-react'
import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { Button } from '@/components/ui/Button'
import { useDismiss } from '@/hooks/useDismiss'
import { cn } from '@/lib/cn'
import { formatLength, type LengthUnit } from '@/lib/units'
import type { Scene } from '../lib/geometry/scene'

interface FitStatusProps {
  scene: Scene
  unit: LengthUnit
  sofaOn: boolean
  onGenerate: () => void
  onHideSofa: () => void
  className?: string
}

/**
 * "● Fits wall" / "▲ Check fit · 2" chip. Opens a small popover with the warnings and quick
 * fixes built from existing actions, so warnings never push the workspace around.
 */
export function FitStatus({ scene, unit, sofaOn, onGenerate, onHideSofa, className }: FitStatusProps) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const panelId = useId()
  const dismiss = useCallback(() => setOpen(false), [])
  useDismiss(rootRef, open, dismiss)

  // Pulse once when the fit state flips, so the change is noticed without a toast.
  const [pulse, setPulse] = useState(false)
  const lastFits = useRef(scene.fits)
  useEffect(() => {
    if (lastFits.current === scene.fits) return
    lastFits.current = scene.fits
    setPulse(true)
    const t = window.setTimeout(() => setPulse(false), 700)
    return () => window.clearTimeout(t)
  }, [scene.fits])

  // Esc closes and returns focus to the chip (document-level: the panel itself isn't a widget).
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      e.preventDefault()
      setOpen(false)
      buttonRef.current?.focus()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open])

  const count = scene.warnings.length
  const tooTall = scene.warnings.some((w) => w.code === 'TOO_TALL')
  const misfit = !scene.fits
  const close = () => {
    setOpen(false)
    buttonRef.current?.focus()
  }
  const a = scene.arrangement
  const aUnit: LengthUnit = unit === 'ft' ? 'in' : unit

  return (
    <div ref={rootRef} className={cn('relative', className)}>
      <button
        ref={buttonRef}
        type="button"
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        aria-label={
          misfit
            ? `Check fit: ${count} ${count === 1 ? 'issue' : 'issues'}`
            : count
              ? `Fits wall, ${count} tip`
              : 'Fits wall'
        }
        onClick={() => setOpen((o) => !o)}
        className={cn(
          'inline-flex h-7 items-center gap-1.5 rounded-full px-2.5 text-xs font-semibold whitespace-nowrap ring-1 transition-[background-color,transform] duration-200',
          misfit
            ? 'bg-gold-100 text-gold-600 ring-gold-300 hover:bg-gold-200/70'
            : 'bg-success-50 text-success-500 ring-success-500/25 hover:bg-success-50/60',
          pulse && 'scale-110',
        )}
      >
        <span aria-hidden className={cn('size-1.5 rounded-full bg-current', misfit && 'animate-pulse')} />
        <span className="max-sm:sr-only">{misfit ? 'Check fit' : 'Fits wall'}</span>
        {count > 0 && (
          <span
            aria-hidden
            className="grid h-4 min-w-4 place-items-center rounded-full bg-current/15 px-1 text-[0.625rem] tabular-nums"
          >
            {count}
          </span>
        )}
      </button>

      {open && (
        <div
          id={panelId}
          role="dialog"
          aria-label="Wall fit"
          className="absolute top-full left-0 z-50 mt-2 w-80 max-w-[calc(100vw-1.5rem)] animate-[pop-in_150ms_ease-out] rounded-xl border border-ivory-300 bg-ivory-50 p-3.5 text-charcoal-700 shadow-pop max-sm:fixed max-sm:inset-x-3 max-sm:top-14 max-sm:w-auto"
        >
          <p className="flex items-center gap-2 text-sm font-semibold text-charcoal-900">
            {misfit ? (
              <CircleAlert aria-hidden className="size-4 text-gold-600" />
            ) : (
              <CircleCheck aria-hidden className="size-4 text-success-500" />
            )}
            {misfit ? 'This arrangement doesn’t fit yet' : 'Fits your wall'}
          </p>
          <p className="mt-1 text-xs text-charcoal-500 tabular-nums">
            Arrangement {formatLength(a.w, aUnit)} × {formatLength(a.h, aUnit)} · covers{' '}
            {Math.round(scene.coverage * 100)}% of the wall
          </p>
          {count > 0 && (
            <ul className="mt-3 flex flex-col gap-2">
              {scene.warnings.map((w) => (
                <li key={w.code} className="flex gap-2 text-[0.8125rem] leading-snug text-charcoal-700">
                  <span aria-hidden className="mt-1.5 size-1.5 shrink-0 rounded-full bg-gold-500" />
                  {w.message}
                </li>
              ))}
            </ul>
          )}
          {misfit && (
            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                size="sm"
                leftIcon={<Sparkles aria-hidden />}
                onClick={() => {
                  onGenerate()
                  close()
                }}
              >
                Find a layout that fits
              </Button>
              {tooTall && sofaOn && (
                <Button
                  variant="quiet"
                  size="sm"
                  leftIcon={<Sofa aria-hidden />}
                  onClick={() => {
                    onHideSofa()
                    close()
                  }}
                >
                  Hide sofa
                </Button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

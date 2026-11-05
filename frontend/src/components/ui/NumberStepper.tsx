import { Minus, Plus } from 'lucide-react'
import { useId, useState, type KeyboardEvent } from 'react'
import { cn } from '@/lib/cn'

interface NumberStepperProps {
  label: string
  /** Visually hide the label (still announced). */
  hideLabel?: boolean
  value: number
  onChange: (value: number) => void
  min: number
  max: number
  step?: number
  /** Unit text inside the field, e.g. "in". */
  unit?: string
  /** Decimal places shown. */
  precision?: number
  disabled?: boolean
  className?: string
}

const roundTo = (v: number, p: number) => Math.round(v * 10 ** p) / 10 ** p

/**
 * "− 3 +" control. Typing is free-form and committed on blur/Enter (clamped to min..max);
 * ArrowUp/ArrowDown step; the buttons disable at the bounds.
 */
export function NumberStepper({
  label,
  hideLabel = false,
  value,
  onChange,
  min,
  max,
  step = 1,
  unit,
  precision = 1,
  disabled = false,
  className,
}: NumberStepperProps) {
  const id = useId()
  const format = (v: number) => String(roundTo(v, precision))
  // While typing, show the raw draft; otherwise always show the current value, so external
  // changes (unit switch, reset, template) appear without syncing effects.
  const [draft, setDraft] = useState<string | null>(null)

  const commit = (next: number) => {
    const clamped = Math.min(max, Math.max(min, roundTo(next, precision)))
    setDraft(null)
    if (clamped !== value) onChange(clamped)
  }

  const onBlur = () => {
    if (draft === null) return
    const parsed = Number.parseFloat(draft.replace(',', '.'))
    if (Number.isFinite(parsed)) commit(parsed)
    else setDraft(null)
  }

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') onBlur()
    if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
      e.preventDefault()
      commit(value + (e.key === 'ArrowUp' ? step : -step))
    }
  }

  // At a bound the button is aria-disabled, not disabled: a disabled button drops keyboard focus
  // mid-press (focus would jump to <body> after holding Enter on "+").
  const atMin = value <= min
  const atMax = value >= max
  const btn =
    'grid size-9 shrink-0 place-items-center rounded-md text-ink-700 transition-colors hover:bg-cream-200 active:bg-cream-300 disabled:cursor-not-allowed disabled:opacity-40 aria-disabled:cursor-not-allowed aria-disabled:opacity-40 aria-disabled:hover:bg-transparent [&>svg]:size-4'

  return (
    <div className={cn('flex min-w-0 items-center justify-between gap-3', className)}>
      <label htmlFor={id} className={cn(hideLabel ? 'sr-only' : 'text-sm font-semibold text-ink-900')}>
        {label}
      </label>
      <div
        className={cn(
          'flex h-10 items-center gap-0.5 rounded-lg border border-cream-600/60 bg-cream-50 p-0.5',
          'focus-within:border-brand-600 focus-within:ring-3 focus-within:ring-brand-600/15',
          'forced-colors:focus-within:outline-2 forced-colors:focus-within:outline-[Highlight]',
          disabled && 'opacity-50',
        )}
      >
        <button
          type="button"
          className={btn}
          onClick={() => !atMin && commit(value - step)}
          disabled={disabled}
          aria-disabled={atMin || undefined}
          aria-label={`Decrease ${label}`}
        >
          <Minus aria-hidden />
        </button>
        <div className="flex items-baseline gap-1 px-1">
          <input
            id={id}
            type="text"
            inputMode="decimal"
            autoComplete="off"
            value={draft ?? format(value)}
            disabled={disabled}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={onBlur}
            onKeyDown={onKeyDown}
            aria-valuemin={min}
            aria-valuemax={max}
            aria-valuenow={value}
            role="spinbutton"
            className="w-10 bg-transparent text-center text-base font-semibold text-ink-900 tabular-nums outline-none"
          />
          {unit && <span className="text-xs text-ink-500">{unit}</span>}
        </div>
        <button
          type="button"
          className={btn}
          onClick={() => !atMax && commit(value + step)}
          disabled={disabled}
          aria-disabled={atMax || undefined}
          aria-label={`Increase ${label}`}
        >
          <Plus aria-hidden />
        </button>
      </div>
    </div>
  )
}

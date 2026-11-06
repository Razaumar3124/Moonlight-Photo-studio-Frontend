import { useId, useState, type KeyboardEvent } from 'react'
import { cn } from '@/lib/cn'
import { fromInches, roundTo, toInches, type LengthUnit } from '@/lib/units'

interface DimensionInputProps {
  label: string
  /** Value in inches (internal unit). */
  valueIn: number
  unit: LengthUnit
  minIn: number
  maxIn: number
  onCommit: (inches: number) => void
  /** Planner density: height follows `--pl-ctl`, the unit is a quiet suffix. */
  compact?: boolean
}

const PRECISION: Record<LengthUnit, number> = { ft: 2, in: 1, cm: 1, m: 2 }
const STEP: Record<LengthUnit, number> = { ft: 0.5, in: 6, cm: 10, m: 0.1 }

/**
 * Wall dimension typed in the chosen unit, stored in inches. Commits on blur/Enter, so the
 * layout doesn't jump on every keystroke; Arrow keys nudge by a sensible step. Out-of-range
 * values are clamped and explained.
 */
export function DimensionInput({
  label,
  valueIn,
  unit,
  minIn,
  maxIn,
  onCommit,
  compact = false,
}: DimensionInputProps) {
  const id = useId()
  const errorId = useId()
  const [draft, setDraft] = useState<string | null>(null)
  // Store the kind of error, not its text, so the range follows a later unit switch.
  const [error, setError] = useState<'range' | 'invalid' | null>(null)
  const display = (inches: number) => String(roundTo(fromInches(inches, unit), PRECISION[unit]))
  const range = `${display(minIn)}–${display(maxIn)} ${unit}`
  const message = error === 'range' ? `Use ${range}.` : `Enter a number between ${range}.`

  const commitInches = (inches: number) => {
    const clamped = Math.min(maxIn, Math.max(minIn, inches))
    setError(Math.abs(clamped - inches) > 1e-6 ? 'range' : null)
    setDraft(null)
    if (Math.abs(clamped - valueIn) > 1e-6) onCommit(clamped)
  }

  const commitDraft = () => {
    if (draft === null) return
    const parsed = Number.parseFloat(draft.replace(',', '.'))
    if (!Number.isFinite(parsed) || parsed <= 0) {
      setError('invalid')
      setDraft(null)
      return
    }
    commitInches(toInches(parsed, unit))
  }

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') commitDraft()
    if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
      e.preventDefault()
      commitInches(valueIn + toInches(e.key === 'ArrowUp' ? STEP[unit] : -STEP[unit], unit))
    }
  }

  return (
    <div className={cn('flex min-w-0 flex-col', compact ? 'gap-1.5' : 'gap-2')}>
      <label
        htmlFor={id}
        className={cn(
          'font-semibold',
          compact ? 'text-[0.8125rem] text-charcoal-700' : 'text-sm text-ink-900',
        )}
      >
        {label}
      </label>
      <div
        className={cn(
          'flex items-center gap-2 rounded-lg border pr-1.5 pl-3',
          compact ? 'h-(--pl-ctl,2.25rem) bg-ivory-50 pr-3' : 'h-11 bg-cream-50 shadow-field',
          'focus-within:border-brand-600 focus-within:ring-3 focus-within:ring-brand-600/15',
          'forced-colors:focus-within:outline-2 forced-colors:focus-within:outline-[Highlight]',
          error ? 'border-danger-600' : 'border-cream-600/60 hover:border-cream-600',
        )}
      >
        <input
          id={id}
          type="text"
          inputMode="decimal"
          autoComplete="off"
          value={draft ?? display(valueIn)}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={commitDraft}
          onKeyDown={onKeyDown}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : undefined}
          className={cn(
            'min-w-0 flex-1 bg-transparent font-semibold tabular-nums outline-none',
            compact ? 'text-base text-charcoal-900 sm:text-sm' : 'text-base text-ink-900',
          )}
        />
        {compact ? (
          <span className="text-xs font-medium text-charcoal-500">{unit}</span>
        ) : (
          <span className="rounded-md bg-brand-600 px-2 py-1 text-xs font-semibold text-white">{unit}</span>
        )}
      </div>
      {error && (
        <p id={errorId} className="text-xs text-danger-600">
          {message}
        </p>
      )}
    </div>
  )
}

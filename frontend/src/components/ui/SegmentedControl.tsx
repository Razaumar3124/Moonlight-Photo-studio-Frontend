import { useId, type ReactNode } from 'react'
import { cn } from '@/lib/cn'

export interface SegmentedOption<T extends string> {
  value: T
  label: ReactNode
  icon?: ReactNode
  /** Accessible name when `label` is not plain text. */
  ariaLabel?: string
}

interface SegmentedControlProps<T extends string> {
  /** Group label (visually hidden unless `showLabel`). */
  label: string
  showLabel?: boolean
  options: readonly SegmentedOption<T>[]
  value: T
  onChange: (value: T) => void
  size?: 'sm' | 'md'
  disabled?: boolean
  className?: string
}

/**
 * Mutually exclusive options ("ft | in | cm | m", "Grid | Salon | Centre | Row").
 * Built on native radio inputs: arrow keys, focus and form semantics come for free.
 */
export function SegmentedControl<T extends string>({
  label,
  showLabel = false,
  options,
  value,
  onChange,
  size = 'md',
  disabled = false,
  className,
}: SegmentedControlProps<T>) {
  const name = useId()
  return (
    <fieldset disabled={disabled} className={cn('min-w-0', className)}>
      <legend className={cn(showLabel ? 'mb-2 text-sm font-semibold text-ink-900' : 'sr-only')}>
        {label}
      </legend>
      <div
        className="grid gap-1.5"
        style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}
      >
        {options.map((opt) => (
          <label key={opt.value} className="relative min-w-0">
            <input
              type="radio"
              name={name}
              value={opt.value}
              checked={opt.value === value}
              onChange={() => onChange(opt.value)}
              aria-label={opt.ariaLabel}
              className="peer sr-only"
            />
            <span
              className={cn(
                'flex w-full cursor-pointer items-center justify-center gap-1 truncate rounded-lg border font-medium transition-colors select-none',
                size === 'sm' ? 'h-9 px-1.5 text-sm' : 'h-10 px-1.5 text-sm',
                'border-cream-300 bg-cream-100 text-ink-700 hover:border-cream-400 hover:bg-cream-200',
                'peer-checked:border-brand-600 peer-checked:bg-brand-600 peer-checked:text-white peer-checked:shadow-button',
                'peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-brand-600',
                'peer-disabled:cursor-not-allowed peer-disabled:opacity-50 [&>svg]:size-3.5 [&>svg]:shrink-0',
              )}
            >
              {opt.icon}
              <span className="truncate">{opt.label}</span>
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}

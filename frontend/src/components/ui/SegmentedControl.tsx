import { useId, type ReactNode } from 'react'
import { cn } from '@/lib/cn'

export interface SegmentedOption<T extends string> {
  value: T
  label: ReactNode
  icon?: ReactNode
  /** Accessible name when `label` is not plain text. */
  ariaLabel?: string
}

type Appearance = 'brand' | 'neutral' | 'stage'

interface SegmentedControlProps<T extends string> {
  /** Group label (visually hidden unless `showLabel`). */
  label: string
  showLabel?: boolean
  labelClassName?: string
  options: readonly SegmentedOption<T>[]
  value: T
  onChange: (value: T) => void
  /** `xs` follows the planner density (`--pl-ctl`). */
  size?: 'xs' | 'sm' | 'md'
  /**
   * `brand`: separate crimson-filled cells (default). `neutral`: a linen track with a white
   * thumb (planner). `stage`: the same on the planner's dark stage.
   */
  appearance?: Appearance
  disabled?: boolean
  className?: string
}

const cellBase =
  'flex w-full cursor-pointer items-center justify-center gap-1.5 truncate font-medium transition-[background-color,color,box-shadow,border-color] duration-150 select-none ' +
  'peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-brand-600 ' +
  'peer-disabled:cursor-not-allowed peer-disabled:opacity-50 [&>svg]:size-3.5 [&>svg]:shrink-0'

const cellByAppearance: Record<Appearance, string> = {
  brand:
    'rounded-lg border border-cream-300 bg-cream-100 text-ink-700 hover:border-cream-400 hover:bg-cream-200 ' +
    'peer-checked:border-brand-600 peer-checked:bg-brand-600 peer-checked:text-white peer-checked:shadow-button',
  neutral:
    'rounded-md text-charcoal-500 hover:text-charcoal-900 ' +
    'peer-checked:bg-white peer-checked:text-charcoal-900 peer-checked:shadow-thumb',
  stage:
    'rounded-md text-ivory-100/75 hover:text-white ' +
    'peer-checked:bg-ivory-50 peer-checked:text-charcoal-900 peer-checked:shadow-thumb',
}

const trackByAppearance: Record<Appearance, string> = {
  brand: 'gap-1.5',
  neutral: 'gap-0.5 rounded-lg bg-ivory-200 p-0.5',
  stage: 'gap-0.5 rounded-lg bg-white/[0.07] p-0.5 ring-1 ring-white/10',
}

const heights = {
  // Track padding is 2px on each side, so the cell is the control height minus 4px.
  xs: 'h-[calc(var(--pl-ctl,2.25rem)-0.25rem)] px-1.5 text-[0.8125rem]',
  sm: 'h-9 px-1.5 text-sm',
  md: 'h-10 px-1.5 text-sm',
}

/**
 * Mutually exclusive options ("ft | in | cm | m", "Grid | Salon | Centre | Row").
 * Built on native radio inputs: arrow keys, focus and form semantics come for free.
 */
export function SegmentedControl<T extends string>({
  label,
  showLabel = false,
  labelClassName,
  options,
  value,
  onChange,
  size = 'md',
  appearance = 'brand',
  disabled = false,
  className,
}: SegmentedControlProps<T>) {
  const name = useId()
  return (
    <fieldset disabled={disabled} className={cn('min-w-0', className)}>
      <legend
        className={cn(showLabel ? cn('mb-2 text-sm font-semibold text-ink-900', labelClassName) : 'sr-only')}
      >
        {label}
      </legend>
      <div
        className={cn('grid', trackByAppearance[appearance])}
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
            <span className={cn(cellBase, cellByAppearance[appearance], heights[size])}>
              {opt.icon}
              <span className="truncate">{opt.label}</span>
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}

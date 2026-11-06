import { ChevronDown } from 'lucide-react'
import { useId, type SelectHTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'children'> {
  label: string
  options: ReadonlyArray<{ value: string; label: string }>
  /** Planner density: control height follows `--pl-ctl`, planner type sizes. */
  compact?: boolean
}

/** Native select (best on mobile) styled like the text fields. */
export function Select({ label, options, className, id, compact = false, ...props }: SelectProps) {
  const autoId = useId()
  const selectId = id ?? autoId
  return (
    <div className={cn('flex flex-col', compact ? 'gap-1.5' : 'gap-2', className)}>
      <label
        htmlFor={selectId}
        className={cn(
          'font-semibold',
          compact ? 'text-[0.8125rem] text-charcoal-700' : 'text-sm text-ink-900',
        )}
      >
        {label}
      </label>
      <div className="relative">
        <select
          id={selectId}
          {...props}
          className={cn(
            'w-full min-w-0 cursor-pointer appearance-none truncate rounded-lg border border-cream-600/60 pr-10 text-base sm:text-sm',
            compact
              ? 'h-(--pl-ctl,2.25rem) bg-ivory-50 pl-3 text-charcoal-900'
              : 'h-11 bg-cream-50 pl-3.5 text-ink-900 shadow-field',
            'hover:border-cream-600 focus:border-brand-600 focus:ring-3 focus:ring-brand-600/15 focus:outline-none',
            'forced-colors:focus:outline-2 forced-colors:focus:outline-[Highlight]',
            'disabled:cursor-not-allowed disabled:opacity-50',
          )}
        >
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <ChevronDown
          aria-hidden
          className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-ink-500"
        />
      </div>
    </div>
  )
}

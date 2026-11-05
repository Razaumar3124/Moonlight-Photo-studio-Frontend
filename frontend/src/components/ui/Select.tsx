import { ChevronDown } from 'lucide-react'
import { useId, type SelectHTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'children'> {
  label: string
  options: ReadonlyArray<{ value: string; label: string }>
}

/** Native select (best on mobile) styled like the text fields. */
export function Select({ label, options, className, id, ...props }: SelectProps) {
  const autoId = useId()
  const selectId = id ?? autoId
  return (
    <div className={cn('flex flex-col gap-2', className)}>
      <label htmlFor={selectId} className="text-sm font-semibold text-ink-900">
        {label}
      </label>
      <div className="relative">
        <select
          id={selectId}
          {...props}
          className={cn(
            'h-11 w-full min-w-0 cursor-pointer appearance-none truncate rounded-lg border border-cream-600/60 bg-cream-50 pr-10 pl-3.5 text-base text-ink-900 shadow-field sm:text-sm',
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

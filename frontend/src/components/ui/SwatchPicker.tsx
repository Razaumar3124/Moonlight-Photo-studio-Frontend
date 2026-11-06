import { Check } from 'lucide-react'
import { useId, type ReactNode } from 'react'
import { cn } from '@/lib/cn'

export interface SwatchOption {
  id: string
  label: string
  hex: string
}

interface SwatchPickerProps {
  label: string
  options: readonly SwatchOption[]
  value: string
  onChange: (id: string) => void
  /** Shown at the right of the label row, e.g. the selected finish name. */
  aside?: ReactNode
  /** Wood-like radial shading instead of a flat paint chip. */
  textured?: boolean
  disabled?: boolean
  /** `sm`: planner chips (26px) with a champagne selection ring and a name tooltip. */
  size?: 'sm' | 'md'
  className?: string
}

/** Perceived brightness, to pick a readable check mark colour. */
function isLight(hex: string) {
  const n = Number.parseInt(hex.replace('#', ''), 16)
  const r = (n >> 16) & 255
  const g = (n >> 8) & 255
  const b = n & 255
  return 0.299 * r + 0.587 * g + 0.114 * b > 160
}

/**
 * Colour chips as a radio group (arrow keys move between colours). Every chip has an accessible
 * name, so screen readers say "Natural Oak, 2 of 8" rather than nothing.
 */
export function SwatchPicker({
  label,
  options,
  value,
  onChange,
  aside,
  textured = false,
  disabled = false,
  size = 'md',
  className,
}: SwatchPickerProps) {
  const name = useId()
  const sm = size === 'sm'
  return (
    <fieldset disabled={disabled} className={cn('min-w-0', className)}>
      <div className={cn('flex items-baseline justify-between gap-3', sm ? 'mb-2' : 'mb-2.5')}>
        <legend
          className={cn('font-semibold', sm ? 'text-[0.8125rem] text-charcoal-700' : 'text-sm text-ink-900')}
        >
          {label}
        </legend>
        {aside && (
          <span
            key={String(aside)}
            className={cn(
              'truncate text-xs font-medium text-gold-600',
              sm && 'animate-[fade-in_180ms_ease-out]',
            )}
          >
            {aside}
          </span>
        )}
      </div>
      <div className={cn('flex flex-wrap', sm ? 'gap-1.5' : 'gap-2')}>
        {options.map((opt, i) => (
          <label key={opt.id} className="group/sw relative" title={sm ? undefined : opt.label}>
            <input
              type="radio"
              name={name}
              value={opt.id}
              checked={opt.id === value}
              onChange={() => onChange(opt.id)}
              aria-label={opt.label}
              className="peer sr-only"
            />
            <span
              className={cn(
                'grid cursor-pointer place-items-center rounded-full border border-black/10 transition-transform duration-150',
                sm
                  ? 'size-6.5 shadow-thumb peer-checked:ring-2 peer-checked:ring-champagne-400 peer-checked:ring-offset-2 peer-checked:ring-offset-ivory-50 hover:scale-110'
                  : 'size-8 shadow-field peer-checked:ring-2 peer-checked:ring-brand-600 peer-checked:ring-offset-2 peer-checked:ring-offset-cream-50 hover:scale-105',
                'peer-focus-visible:outline-2 peer-focus-visible:outline-offset-4 peer-focus-visible:outline-brand-600',
                'peer-disabled:cursor-not-allowed peer-disabled:opacity-40 peer-disabled:hover:scale-100',
                '[&>svg]:opacity-0 peer-checked:[&>svg]:opacity-100',
              )}
              style={{
                background: textured
                  ? `radial-gradient(circle at 35% 30%, color-mix(in srgb, ${opt.hex} 70%, white) 0%, ${opt.hex} 45%, color-mix(in srgb, ${opt.hex} 75%, black) 100%)`
                  : opt.hex,
              }}
            >
              <Check
                aria-hidden
                className={cn(sm ? 'size-3' : 'size-4', isLight(opt.hex) ? 'text-ink-900' : 'text-white')}
                strokeWidth={3}
              />
            </span>
            {sm && (
              <span
                aria-hidden
                className={cn(
                  // display:none until hovered, so it never widens a scrolling rail; the later
                  // half of the row aligns right so edge swatches stay inside the panel.
                  'pointer-events-none absolute bottom-full z-40 mb-2 hidden animate-[fade-in_150ms_ease-out_300ms_both] rounded-md bg-charcoal-900 px-2 py-1 text-[0.6875rem] font-medium whitespace-nowrap text-ivory-50 shadow-pop [@media(hover:hover)]:group-hover/sw:block',
                  i < options.length / 2 ? 'left-0' : 'right-0',
                )}
              >
                {opt.label}
              </span>
            )}
          </label>
        ))}
      </div>
    </fieldset>
  )
}

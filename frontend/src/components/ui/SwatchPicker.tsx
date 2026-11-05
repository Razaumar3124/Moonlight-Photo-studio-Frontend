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
  className,
}: SwatchPickerProps) {
  const name = useId()
  return (
    <fieldset disabled={disabled} className={cn('min-w-0', className)}>
      <div className="mb-2.5 flex items-baseline justify-between gap-3">
        <legend className="text-sm font-semibold text-ink-900">{label}</legend>
        {aside && <span className="truncate text-xs font-medium text-gold-600">{aside}</span>}
      </div>
      <div className="flex flex-wrap gap-2">
        {options.map((opt) => (
          <label key={opt.id} className="relative" title={opt.label}>
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
                'grid size-8 cursor-pointer place-items-center rounded-full border border-black/10 shadow-field transition-transform',
                'peer-checked:ring-2 peer-checked:ring-brand-600 peer-checked:ring-offset-2 peer-checked:ring-offset-cream-50 hover:scale-105',
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
                className={cn('size-4', isLight(opt.hex) ? 'text-ink-900' : 'text-white')}
                strokeWidth={3}
              />
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}

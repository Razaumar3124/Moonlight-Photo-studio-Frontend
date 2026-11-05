import { useId, type ReactNode } from 'react'
import { cn } from '@/lib/cn'

interface SwitchProps {
  label: ReactNode
  description?: ReactNode
  checked: boolean
  onChange: (checked: boolean) => void
  /** Decorative icon before the label. */
  icon?: ReactNode
  disabled?: boolean
  className?: string
}

/** On/off setting row: label (+ description) on the left, a crimson switch on the right. */
export function Switch({ label, description, checked, onChange, icon, disabled, className }: SwitchProps) {
  const labelId = useId()
  const descId = useId()
  return (
    <div className={cn('flex items-center gap-3', className)}>
      {icon && (
        <span aria-hidden className="flex shrink-0 text-ink-500 [&>svg]:size-[1.125rem]">
          {icon}
        </span>
      )}
      <div className="min-w-0 flex-1">
        <span id={labelId} className="block text-sm font-medium text-ink-900">
          {label}
        </span>
        {description && (
          <span id={descId} className="block text-xs text-ink-500">
            {description}
          </span>
        )}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-labelledby={labelId}
        aria-describedby={description ? descId : undefined}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          'relative inline-flex h-7 w-12 shrink-0 items-center rounded-full border transition-colors duration-200',
          'before:absolute before:-inset-2 before:content-[""]', // 44px-ish hit area
          checked ? 'border-brand-700 bg-brand-600' : 'border-cream-400 bg-cream-300',
          'disabled:cursor-not-allowed disabled:opacity-50',
          'forced-colors:border-[ButtonText]',
        )}
      >
        <span
          aria-hidden
          className={cn(
            'size-5 rounded-full bg-white shadow-md transition-transform duration-200',
            checked ? 'translate-x-6' : 'translate-x-1',
          )}
        />
      </button>
    </div>
  )
}

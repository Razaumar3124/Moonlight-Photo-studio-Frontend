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
  /** `sm`: 20×36 planner switch with charcoal "on" state and planner type sizes. */
  size?: 'sm' | 'md'
  className?: string
}

/** On/off setting row: label (+ description) on the left, the switch on the right. */
export function Switch({
  label,
  description,
  checked,
  onChange,
  icon,
  disabled,
  size = 'md',
  className,
}: SwitchProps) {
  const labelId = useId()
  const descId = useId()
  const sm = size === 'sm'
  return (
    <div className={cn('flex items-center gap-3', disabled && 'opacity-60', className)}>
      {icon && (
        <span
          aria-hidden
          className={cn(
            'flex shrink-0 [&>svg]:size-[1.125rem]',
            sm ? 'text-charcoal-500 [&>svg]:size-4' : 'text-ink-500',
          )}
        >
          {icon}
        </span>
      )}
      <div className="min-w-0 flex-1">
        <span
          id={labelId}
          className={cn(
            'block font-medium',
            sm ? 'text-[0.8125rem] text-charcoal-900' : 'text-sm text-ink-900',
          )}
        >
          {label}
        </span>
        {description && (
          <span id={descId} className={cn('block text-xs', sm ? 'text-charcoal-500' : 'text-ink-500')}>
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
          'relative inline-flex shrink-0 items-center rounded-full border transition-colors duration-200',
          'before:absolute before:-inset-2 before:content-[""]', // 44px-ish hit area
          sm ? 'h-5 w-9' : 'h-7 w-12',
          checked
            ? sm
              ? 'border-charcoal-900 bg-charcoal-900'
              : 'border-brand-700 bg-brand-600'
            : sm
              ? 'border-ivory-300 bg-ivory-300 hover:bg-charcoal-300/60'
              : 'border-cream-400 bg-cream-300',
          'disabled:cursor-not-allowed',
          'forced-colors:border-[ButtonText]',
        )}
      >
        <span
          aria-hidden
          className={cn(
            'rounded-full bg-white shadow-md transition-transform duration-200',
            sm ? 'size-4' : 'size-5',
            checked ? (sm ? 'translate-x-4' : 'translate-x-6') : sm ? 'translate-x-0.5' : 'translate-x-1',
          )}
        />
      </button>
    </div>
  )
}

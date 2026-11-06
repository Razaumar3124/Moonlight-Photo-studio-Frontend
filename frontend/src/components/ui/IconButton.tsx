import type { ButtonHTMLAttributes, ReactNode, Ref } from 'react'
import { cn } from '@/lib/cn'

type IconButtonVariant = 'ghost' | 'outline' | 'solid' | 'glass' | 'quiet' | 'stage'

const variants: Record<IconButtonVariant, string> = {
  ghost: 'text-ink-700 hover:bg-cream-200 active:bg-cream-300',
  outline:
    'border border-cream-300 bg-cream-50 text-ink-700 shadow-field hover:border-cream-400 hover:bg-white active:bg-cream-200',
  solid: 'bg-brand-600 text-white shadow-button hover:bg-brand-700 active:bg-brand-800',
  glass: 'border border-white/25 bg-white/10 text-white backdrop-blur hover:bg-white/20 active:bg-white/25',
  /** Planner: charcoal icon on ivory. */
  quiet: 'text-charcoal-700 hover:bg-ivory-200 hover:text-charcoal-900 active:bg-ivory-300',
  /** Planner: light icon on the dark stage. */
  stage: 'text-ivory-100/80 hover:bg-white/10 hover:text-white active:bg-white/15',
}

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Required: icon-only buttons need an accessible name. */
  label: string
  icon: ReactNode
  variant?: IconButtonVariant
  size?: 'xs' | 'sm' | 'md' | 'lg'
  shape?: 'round' | 'square'
  /**
   * Styled tooltip (hover after a short delay, and immediately on keyboard focus) instead of the
   * native `title`, which never shows for keyboard users. Side it opens towards.
   */
  tooltip?: 'top' | 'bottom' | false
  tooltipAlign?: 'center' | 'end'
  ref?: Ref<HTMLButtonElement>
}

const sizes = {
  xs: 'size-7 [&>svg]:size-4',
  sm: 'size-8 [&>svg]:size-4',
  md: 'size-10 [&>svg]:size-5',
  lg: 'size-12 [&>svg]:size-5',
}

/** Icon-only button. `label` becomes aria-label and the tooltip. */
export function IconButton({
  label,
  icon,
  variant = 'ghost',
  size = 'md',
  shape = 'round',
  tooltip = false,
  tooltipAlign = 'center',
  className,
  type = 'button',
  ...props
}: IconButtonProps) {
  return (
    <button
      type={type}
      aria-label={label}
      title={tooltip ? undefined : label}
      className={cn(
        'group/ib relative inline-grid shrink-0 place-items-center transition-[background-color,border-color,color,transform] duration-150 active:scale-95',
        shape === 'round' ? 'rounded-full' : 'rounded-lg',
        'disabled:pointer-events-none disabled:opacity-40',
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    >
      {icon}
      {tooltip && (
        <Tooltip side={tooltip} align={tooltipAlign}>
          {label}
        </Tooltip>
      )}
    </button>
  )
}

/**
 * Visual-only tooltip for a parent with `group/ib` (the accessible name comes from aria-label).
 * Shown on hover (400 ms delay) and on keyboard focus; hidden on touch-only devices.
 */
export function Tooltip({
  side = 'bottom',
  align = 'center',
  children,
}: {
  side?: 'top' | 'bottom'
  /** `end`: right-aligned to the button, for buttons at the right edge of a panel. */
  align?: 'center' | 'end'
  children: ReactNode
}) {
  return (
    <span
      aria-hidden
      className={cn(
        // display:none until shown: a hidden (opacity-0) tooltip would still widen scroll containers.
        'pointer-events-none absolute z-50 hidden animate-[fade-in_150ms_ease-out_both] rounded-md bg-charcoal-900 px-2 py-1 text-[0.6875rem] leading-tight font-medium whitespace-nowrap text-ivory-50 shadow-pop',
        'group-focus-visible/ib:block group-focus-visible/ib:[animation-delay:0ms]',
        '[@media(hover:hover)]:group-hover/ib:block [@media(hover:hover)]:group-hover/ib:[animation-delay:400ms]',
        side === 'bottom' ? 'top-full mt-1.5' : 'bottom-full mb-1.5',
        align === 'end' ? 'right-0' : 'left-1/2 -translate-x-1/2',
      )}
    >
      {children}
    </span>
  )
}

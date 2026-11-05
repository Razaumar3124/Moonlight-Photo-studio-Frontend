import type { ButtonHTMLAttributes, ReactNode, Ref } from 'react'
import { cn } from '@/lib/cn'

type IconButtonVariant = 'ghost' | 'outline' | 'solid' | 'glass'

const variants: Record<IconButtonVariant, string> = {
  ghost: 'text-ink-700 hover:bg-cream-200 active:bg-cream-300',
  outline:
    'border border-cream-300 bg-cream-50 text-ink-700 shadow-field hover:border-cream-400 hover:bg-white active:bg-cream-200',
  solid: 'bg-brand-600 text-white shadow-button hover:bg-brand-700 active:bg-brand-800',
  glass: 'border border-white/25 bg-white/10 text-white backdrop-blur hover:bg-white/20 active:bg-white/25',
}

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  /** Required: icon-only buttons need an accessible name. */
  label: string
  icon: ReactNode
  variant?: IconButtonVariant
  size?: 'sm' | 'md' | 'lg'
  ref?: Ref<HTMLButtonElement>
}

const sizes = { sm: 'size-8 [&>svg]:size-4', md: 'size-10 [&>svg]:size-5', lg: 'size-12 [&>svg]:size-5' }

/** Icon-only button. `label` becomes aria-label and the tooltip. */
export function IconButton({
  label,
  icon,
  variant = 'ghost',
  size = 'md',
  className,
  type = 'button',
  ...props
}: IconButtonProps) {
  return (
    <button
      type={type}
      aria-label={label}
      title={label}
      className={cn(
        'inline-grid shrink-0 place-items-center rounded-full transition-[background-color,border-color,transform] duration-150 active:scale-95',
        'disabled:pointer-events-none disabled:opacity-40',
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    >
      {icon}
    </button>
  )
}

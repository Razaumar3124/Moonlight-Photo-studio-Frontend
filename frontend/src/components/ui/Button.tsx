import type { ButtonHTMLAttributes, ReactNode, Ref } from 'react'
import { Spinner } from '@/components/feedback/Spinner'
import { cn } from '@/lib/cn'

type ButtonVariant = 'primary' | 'primary-gradient' | 'secondary' | 'ghost'
type ButtonSize = 'md' | 'lg'

const base =
  'inline-flex items-center justify-center gap-2.5 rounded-field font-semibold whitespace-nowrap ' +
  'transition-[background-color,border-color,box-shadow,color] duration-150 ' +
  'disabled:cursor-not-allowed disabled:opacity-60 aria-busy:cursor-progress aria-busy:opacity-90'

const variants: Record<ButtonVariant, string> = {
  primary:
    'bg-brand-600 text-white shadow-button hover:bg-brand-700 active:bg-brand-800 ' +
    'disabled:hover:bg-brand-600',
  // Register CTA in the mockup: crimson with a soft lighter sheen towards the right.
  'primary-gradient':
    'bg-brand-600 bg-linear-to-r from-brand-800 via-brand-600 to-brand-500 text-white shadow-button ' +
    'hover:from-brand-900 hover:via-brand-700 hover:to-brand-600 active:from-brand-900 active:to-brand-700',
  secondary:
    'border border-cream-300 bg-white text-ink-900 shadow-field hover:border-cream-400 hover:bg-cream-50 ' +
    'active:bg-cream-200',
  ghost: 'text-ink-700 hover:bg-cream-200 active:bg-cream-300',
}

const sizes: Record<ButtonSize, string> = {
  md: 'h-11 px-4 text-sm',
  lg: 'h-12 px-5 text-base',
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant
  size?: ButtonSize
  fullWidth?: boolean
  /** Icon before the label. Replaced by a spinner while `loading`. */
  leftIcon?: ReactNode
  /** Shows a spinner, sets aria-busy and blocks clicks. */
  loading?: boolean
  /** Label while loading, e.g. "Signing in…". Defaults to the normal children. */
  loadingText?: ReactNode
  ref?: Ref<HTMLButtonElement>
}

export function Button({
  variant = 'primary',
  size = 'md',
  fullWidth = false,
  leftIcon,
  loading = false,
  loadingText,
  type = 'button',
  disabled,
  className,
  children,
  onClick,
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      // Stay focusable while loading (no `disabled`) so focus isn't lost mid-submit.
      disabled={disabled}
      aria-busy={loading || undefined}
      onClick={loading ? (e) => e.preventDefault() : onClick}
      className={cn(base, variants[variant], sizes[size], fullWidth && 'w-full', className)}
      {...props}
    >
      {loading ? <Spinner className="size-5" /> : leftIcon}
      <span>{loading && loadingText ? loadingText : children}</span>
    </button>
  )
}

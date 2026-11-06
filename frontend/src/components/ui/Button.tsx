import type { ButtonHTMLAttributes, ReactNode, Ref } from 'react'
import { Spinner } from '@/components/feedback/Spinner'
import { cn } from '@/lib/cn'

type ButtonVariant =
  | 'primary'
  | 'primary-gradient'
  | 'secondary'
  | 'ghost'
  /** Charcoal solid: the strong neutral CTA (planner "Request a Quote"). */
  | 'dark'
  /** Planner secondary: ivory with a hairline, charcoal text. */
  | 'quiet'
  /** Light-on-dark, for controls sitting on the planner's dark stage. */
  | 'stage'
/** `compact` follows the planner density (`--pl-ctl`), `sm` is a fixed 32px. */
type ButtonSize = 'sm' | 'compact' | 'md' | 'lg'

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
  dark:
    'bg-charcoal-900 text-ivory-50 shadow-[0_6px_16px_-8px_rgb(31_27_25/0.6)] hover:bg-charcoal-800 ' +
    'active:bg-black disabled:hover:bg-charcoal-900',
  quiet:
    'border border-ivory-300 bg-ivory-50 text-charcoal-900 hover:border-charcoal-300/70 hover:bg-white ' +
    'active:bg-ivory-200',
  stage:
    'border border-white/12 bg-white/[0.06] text-ivory-100 hover:border-white/25 hover:bg-white/12 ' +
    'hover:text-white active:bg-white/16',
}

const sizes: Record<ButtonSize, string> = {
  sm: 'h-8 gap-1.5 rounded-lg px-3 text-[0.8125rem] [&>svg]:size-4',
  compact: 'h-(--pl-ctl,2.25rem) gap-2 rounded-lg px-3.5 text-[0.8125rem] [&>svg]:size-4',
  md: 'h-11 px-4 text-sm',
  // Optional page density (auth pages set these in `.auth-scope`); defaults are 48px / 16px.
  lg: 'h-[var(--button-lg-h,3rem)] px-5 text-[length:var(--button-lg-size,1rem)] leading-normal',
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

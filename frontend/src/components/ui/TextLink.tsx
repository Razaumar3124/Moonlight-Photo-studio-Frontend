import { Link, type LinkProps } from 'react-router-dom'
import { cn } from '@/lib/cn'

/** In-app link in brand crimson ("Create an account", "Forgot Password?"). */
export function TextLink({ className, ...props }: LinkProps) {
  return (
    <Link
      className={cn(
        'rounded-sm font-semibold text-brand-600 underline decoration-brand-600/40 underline-offset-3',
        'transition-colors hover:text-brand-700 hover:decoration-brand-700',
        className,
      )}
      {...props}
    />
  )
}

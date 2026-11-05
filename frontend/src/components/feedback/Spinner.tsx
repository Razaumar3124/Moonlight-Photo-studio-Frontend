import { LoaderCircle } from 'lucide-react'
import { cn } from '@/lib/cn'

interface SpinnerProps {
  className?: string
  /** Screen-reader text. Omit when the surrounding element already says what's loading. */
  label?: string
}

export function Spinner({ className, label }: SpinnerProps) {
  return (
    <>
      <LoaderCircle aria-hidden className={cn('size-5 animate-spin', className)} />
      {label && <span className="sr-only">{label}</span>}
    </>
  )
}

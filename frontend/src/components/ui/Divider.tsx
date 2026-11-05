import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'

interface DividerProps {
  /** Centred label, e.g. "OR". Omit for a plain rule. */
  label?: ReactNode
  className?: string
}

/**
 * Thin warm rule; with a label it becomes the "—— OR ——" separator from the auth designs.
 * The labelled version is plain text between decorative lines (not role="separator", whose
 * children are presentational), so screen readers still read "or" between the two options.
 */
export function Divider({ label, className }: DividerProps) {
  if (!label) return <hr className={cn('border-0 border-t border-cream-300', className)} />

  return (
    <div className={cn('flex items-center gap-4', className)}>
      <span aria-hidden className="h-px flex-1 bg-linear-to-r from-transparent to-gold-200" />
      <span className="text-xs font-medium tracking-[0.15em] text-ink-500 uppercase">{label}</span>
      <span aria-hidden className="h-px flex-1 bg-linear-to-l from-transparent to-gold-200" />
    </div>
  )
}

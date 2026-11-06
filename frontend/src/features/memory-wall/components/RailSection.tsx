import { useId, type ReactNode } from 'react'
import { cn } from '@/lib/cn'

interface RailSectionProps {
  /** Champagne eyebrow before the title ("01") or a small icon. */
  numeral?: ReactNode
  title: ReactNode
  /** Right side of the heading row: a value or a small action. */
  aside?: ReactNode
  className?: string
  children: ReactNode
}

/**
 * A section of a planner rail: numeral + serif title, then its controls. Sections are separated
 * by hairlines inside the rail, never boxed as cards.
 */
export function RailSection({ numeral, title, aside, className, children }: RailSectionProps) {
  const titleId = useId()
  return (
    <section
      aria-labelledby={titleId}
      className={cn('flex flex-col gap-[calc(var(--pl-gap)*0.66)]', className)}
    >
      <header className="flex min-h-6 items-center justify-between gap-2">
        <h2 className="flex min-w-0 items-center gap-2 leading-none">
          {numeral !== undefined && (
            <span
              aria-hidden
              className="font-sans text-[0.6875rem] font-semibold tracking-[0.18em] text-gold-600 tabular-nums"
            >
              {numeral}
            </span>
          )}
          <span
            id={titleId}
            className="truncate font-display text-[1.0625rem] font-semibold text-charcoal-900"
          >
            {title}
          </span>
        </h2>
        {aside}
      </header>
      {children}
    </section>
  )
}

/** Scrollable rail column; sections get hairline separators. */
export function Rail({
  label,
  side,
  className,
  children,
}: {
  label: string
  side: 'left' | 'right'
  className?: string
  children: ReactNode
}) {
  return (
    <aside
      aria-label={label}
      className={cn(
        'relative flex min-h-0 min-w-0 scroll-quiet flex-col overflow-y-auto overscroll-contain bg-ivory-50 p-(--pl-pad)',
        side === 'left' ? 'border-r border-ivory-300' : 'border-l border-ivory-300',
        '[&>section+section]:mt-(--pl-gap) [&>section+section]:border-t [&>section+section]:border-ivory-300 [&>section+section]:pt-(--pl-gap)',
        className,
      )}
    >
      {children}
    </aside>
  )
}

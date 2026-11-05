import { cn } from '@/lib/cn'

/**
 * "— EST. 1985 —" eyebrow shown under the logo. Text uses gold-600 (4.6:1) rather than the
 * mockup's lighter gold (3.2:1) so the small caps pass WCAG AA; the rules stay gold-400.
 */
export function EstablishedTag({ className }: { className?: string }) {
  return (
    <p
      className={cn(
        'flex items-center gap-2.5 text-xs font-semibold tracking-[0.25em] text-gold-600 uppercase sm:text-sm',
        className,
      )}
    >
      <span aria-hidden className="h-px w-4 bg-gold-400" />
      <span>Est. 1985</span>
      <span aria-hidden className="h-px w-4 bg-gold-400" />
    </p>
  )
}

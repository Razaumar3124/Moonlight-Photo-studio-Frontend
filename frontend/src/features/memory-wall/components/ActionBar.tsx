import { cn } from '@/lib/cn'
import { RequestQuoteButton } from './PlannerHeader'
import { GenerateCluster, type GenerateHandlers } from './Stage'

/**
 * Phone bottom bar: the two actions people need most on a small screen, Generate (with
 * Regenerate and Redesign) and Request a Quote. Templates, My Designs and Save sit
 * in the header's More menu. Hidden while typing so it never rides on the on-screen keyboard.
 */
export function MobileActionBar({
  onQuote,
  hidden = false,
  ...generate
}: GenerateHandlers & {
  onQuote: () => void
  hidden?: boolean
}) {
  return (
    <nav
      aria-label="Design actions"
      className={cn(
        'relative z-20 flex shrink-0 items-center gap-1.5 border-t border-ivory-300 bg-ivory-50 px-2 pt-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] shadow-[0_-6px_20px_-12px_rgb(31_27_25/0.25)]',
        hidden && 'hidden',
      )}
    >
      <GenerateCluster tone="bar" className="min-w-0 flex-1" {...generate} />
      <RequestQuoteButton short onClick={onQuote} className="h-11 px-3.5 text-sm" />
    </nav>
  )
}

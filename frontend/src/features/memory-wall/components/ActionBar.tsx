import { Bookmark, ChevronRight, LayoutGrid, Maximize2 } from 'lucide-react'
import type { ReactNode } from 'react'

interface ActionBarProps {
  onFullscreen: () => void
  onTemplates: () => void
  onSaved: () => void
  onQuote: () => void
}

const ITEMS = (p: ActionBarProps) =>
  [
    {
      icon: <Maximize2 />,
      title: 'Preview Fullscreen',
      short: 'Preview',
      subtitle: 'View large & download',
      onClick: p.onFullscreen,
    },
    {
      icon: <LayoutGrid />,
      title: 'All Templates',
      short: 'Templates',
      subtitle: 'Explore layout templates',
      onClick: p.onTemplates,
    },
    {
      icon: <Bookmark />,
      title: 'My Saved Templates',
      short: 'Saved',
      subtitle: 'View your designs',
      onClick: p.onSaved,
    },
  ] as const

/**
 * Bottom actions. Desktop/tablet: a card row like the mockup (Download moved into the
 * fullscreen preview). Phones: a fixed bar with icon buttons and the quote CTA.
 */
export function ActionBar(props: ActionBarProps) {
  const items = ITEMS(props)
  return (
    <>
      <nav
        aria-label="Design actions"
        className="hidden gap-3 rounded-card border border-cream-300 bg-cream-50 p-3 shadow-card md:grid md:grid-cols-3 xl:grid-cols-[repeat(3,minmax(0,1fr))_minmax(0,1.3fr)]"
      >
        {items.map((it) => (
          <button
            key={it.title}
            type="button"
            onClick={it.onClick}
            className="group flex min-w-0 items-center gap-3 rounded-xl border border-cream-300 bg-white px-4 py-3 text-left shadow-field transition-[border-color,box-shadow,transform] hover:-translate-y-0.5 hover:border-brand-200 hover:shadow-card"
          >
            <span
              aria-hidden
              className="shrink-0 text-brand-600 transition-transform group-hover:scale-110 [&>svg]:size-6"
            >
              {it.icon}
            </span>
            <span className="min-w-0">
              <span className="block truncate font-display text-base font-semibold text-ink-900">
                {it.title}
              </span>
              <span className="block truncate text-xs text-ink-500">{it.subtitle}</span>
            </span>
          </button>
        ))}
        <QuoteButton
          onClick={props.onQuote}
          className="h-full min-h-14 text-xl md:col-span-3 xl:col-span-1"
        />
      </nav>

      {/* Phones */}
      <nav
        aria-label="Design actions"
        className="fixed inset-x-0 bottom-0 z-40 flex items-center gap-1 border-t border-cream-300 bg-cream-50/95 px-3 pt-2 pb-[max(0.5rem,env(safe-area-inset-bottom))] shadow-[0_-4px_20px_rgb(74_10_13/0.08)] backdrop-blur md:hidden"
      >
        {items.map((it) => (
          <MobileAction key={it.title} icon={it.icon} label={it.short} onClick={it.onClick} />
        ))}
        <QuoteButton
          onClick={props.onQuote}
          className="ml-auto h-12 min-w-0 flex-1 px-2 text-sm min-[360px]:px-3 min-[360px]:text-base"
        />
      </nav>
    </>
  )
}

function MobileAction({ icon, label, onClick }: { icon: ReactNode; label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="flex w-12 shrink-0 flex-col items-center gap-0.5 rounded-lg py-1 text-[0.5625rem] leading-tight font-medium text-ink-700 active:bg-cream-200 min-[360px]:w-16 min-[360px]:text-[0.625rem] [&>svg]:size-5 [&>svg]:text-brand-600"
    >
      {icon}
      <span className="w-full truncate text-center">{label}</span>
    </button>
  )
}

function QuoteButton({ onClick, className }: { onClick: () => void; className?: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex items-center justify-center gap-2 rounded-xl bg-brand-600 bg-linear-to-r from-brand-700 to-brand-600 font-display font-semibold text-white shadow-button transition-[filter,transform] hover:brightness-110 active:scale-[0.98] ${className ?? ''}`}
    >
      <span className="whitespace-nowrap">Request a Quote</span>
      <ChevronRight aria-hidden className="hidden size-5 shrink-0 min-[360px]:block md:block" />
    </button>
  )
}

import { useRef, type KeyboardEvent, type ReactNode } from 'react'
import { cn } from '@/lib/cn'

export interface TabItem<T extends string> {
  id: T
  label: ReactNode
  icon?: ReactNode
  /** Accessible name when `label` is hidden at some widths. */
  ariaLabel?: string
}

const tabDomId = (base: string, id: string) => `${base}-tab-${id}`
const panelDomId = (base: string, id: string) => `${base}-panel-${id}`

interface TabsProps<T extends string> {
  /** Unique prefix for tab/panel ids (use useId()). */
  idBase: string
  label: string
  tabs: readonly TabItem<T>[]
  value: T
  onChange: (id: T) => void
  /** `segmented`: linen track with a white thumb. `underline`: text tabs with a red rule. */
  appearance?: 'segmented' | 'underline'
  className?: string
}

/**
 * WAI-ARIA tabs with automatic activation: ←/→ (and Home/End) move and select, only the
 * selected tab is in the Tab order.
 */
export function Tabs<T extends string>({
  idBase,
  label,
  tabs,
  value,
  onChange,
  appearance = 'segmented',
  className,
}: TabsProps<T>) {
  const listRef = useRef<HTMLDivElement>(null)

  const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
    const i = tabs.findIndex((t) => t.id === value)
    const go = (n: number) => {
      const next = tabs[(n + tabs.length) % tabs.length]
      if (!next) return
      e.preventDefault()
      onChange(next.id)
      listRef.current?.querySelector<HTMLElement>(`#${CSS.escape(tabDomId(idBase, next.id))}`)?.focus()
    }
    if (e.key === 'ArrowRight') go(i + 1)
    else if (e.key === 'ArrowLeft') go(i - 1)
    else if (e.key === 'Home') go(0)
    else if (e.key === 'End') go(tabs.length - 1)
  }

  return (
    <div
      ref={listRef}
      role="tablist"
      aria-label={label}
      className={cn(
        'grid',
        appearance === 'segmented'
          ? 'gap-0.5 rounded-lg bg-ivory-200 p-0.5'
          : 'gap-1 border-b border-ivory-300',
        className,
      )}
      style={{ gridTemplateColumns: `repeat(${tabs.length}, minmax(0, 1fr))` }}
    >
      {tabs.map((t) => {
        const selected = t.id === value
        return (
          <button
            key={t.id}
            id={tabDomId(idBase, t.id)}
            type="button"
            role="tab"
            aria-selected={selected}
            aria-controls={panelDomId(idBase, t.id)}
            aria-label={t.ariaLabel}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(t.id)}
            onKeyDown={onKeyDown}
            className={cn(
              'flex min-w-0 items-center justify-center gap-1.5 text-[0.8125rem] font-medium transition-[background-color,color,box-shadow] duration-150 [&>svg]:size-4 [&>svg]:shrink-0',
              appearance === 'segmented'
                ? cn(
                    'h-[calc(var(--pl-ctl,2.25rem)-0.25rem)] rounded-md px-2',
                    selected
                      ? 'bg-white text-charcoal-900 shadow-thumb'
                      : 'text-charcoal-500 hover:text-charcoal-900',
                  )
                : cn(
                    '-mb-px h-10 border-b-2 px-1',
                    selected
                      ? 'border-brand-600 text-charcoal-900'
                      : 'border-transparent text-charcoal-500 hover:text-charcoal-900',
                  ),
            )}
          >
            {t.icon}
            <span className="truncate">{t.label}</span>
          </button>
        )
      })}
    </div>
  )
}

/** Panel for one tab. Inactive panels stay mounted (state such as upload errors survives). */
export function TabPanel({
  idBase,
  id,
  active,
  className,
  children,
}: {
  idBase: string
  id: string
  active: boolean
  className?: string
  children: ReactNode
}) {
  return (
    <div
      id={panelDomId(idBase, id)}
      role="tabpanel"
      aria-labelledby={tabDomId(idBase, id)}
      hidden={!active}
      tabIndex={-1}
      className={cn(active && 'animate-[fade-in_160ms_ease-out]', 'outline-none', className)}
    >
      {children}
    </div>
  )
}

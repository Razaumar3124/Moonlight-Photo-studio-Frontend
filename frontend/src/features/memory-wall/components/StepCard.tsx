import { ChevronDown } from 'lucide-react'
import { useId, useState, type ReactNode } from 'react'
import { cn } from '@/lib/cn'

interface StepCardProps {
  /** Number in the crimson step badge, or an icon instead. */
  step?: number
  icon?: ReactNode
  title: string
  subtitle?: string
  badge?: ReactNode
  /** Header controls on the right (when not collapsible). */
  actions?: ReactNode
  /** Header becomes a disclosure button (accordion on phones, "Preview Settings" everywhere). */
  collapsible?: boolean
  defaultOpen?: boolean
  className?: string
  bodyClassName?: string
  children: ReactNode
}

/** Numbered planner panel from the mockup: "① Wall Configuration". */
export function StepCard({
  step,
  icon,
  title,
  subtitle,
  badge,
  actions,
  collapsible = false,
  defaultOpen = true,
  className,
  bodyClassName,
  children,
}: StepCardProps) {
  const [open, setOpen] = useState(defaultOpen)
  const titleId = useId()
  const bodyId = useId()
  const expanded = !collapsible || open

  const heading = (
    <span className="flex min-w-0 items-start gap-3 text-left">
      {step !== undefined ? (
        <span
          aria-hidden
          className="grid size-8 shrink-0 place-items-center rounded-full bg-brand-600 font-display text-base font-semibold text-white shadow-button ring-2 ring-brand-100"
        >
          {step}
        </span>
      ) : (
        icon && (
          <span aria-hidden className="grid size-8 shrink-0 place-items-center text-gold-500 [&>svg]:size-6">
            {icon}
          </span>
        )
      )}
      <span className="min-w-0">
        <span id={titleId} className="block font-display text-xl leading-tight font-semibold text-brand-700">
          {title}
        </span>
        {subtitle && <span className="mt-0.5 block text-xs text-ink-500">{subtitle}</span>}
      </span>
    </span>
  )

  return (
    <section
      aria-labelledby={titleId}
      className={cn('rounded-card border border-cream-300 bg-cream-50 p-4 shadow-card', className)}
    >
      <header className="flex items-start justify-between gap-3">
        {collapsible ? (
          <button
            type="button"
            aria-expanded={open}
            aria-controls={bodyId}
            onClick={() => setOpen((o) => !o)}
            className="-m-1 flex min-w-0 flex-1 items-start justify-between gap-3 rounded-lg p-1"
          >
            {heading}
            <ChevronDown
              aria-hidden
              className={cn('mt-1.5 size-5 shrink-0 text-ink-500 transition-transform', open && 'rotate-180')}
            />
          </button>
        ) : (
          <>
            {heading}
            {(badge || actions) && (
              <div className="flex shrink-0 items-center gap-2">
                {badge}
                {actions}
              </div>
            )}
          </>
        )}
        {collapsible && badge}
      </header>
      {expanded && (
        <div id={bodyId} className={cn('mt-4 flex flex-col gap-4', bodyClassName)}>
          {children}
        </div>
      )}
    </section>
  )
}

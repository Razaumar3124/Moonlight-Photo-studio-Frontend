import { Check } from 'lucide-react'
import { useCallback, useEffect, useId, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { useDismiss } from '@/hooks/useDismiss'
import { cn } from '@/lib/cn'
import { Tooltip } from './IconButton'

export interface MenuItem {
  id: string
  label: ReactNode
  description?: ReactNode
  icon?: ReactNode
  onSelect: () => void
  /** `radio` / `checkbox` items expose `checked` (menuitemradio / menuitemcheckbox). */
  kind?: 'item' | 'radio' | 'checkbox'
  checked?: boolean
  danger?: boolean
  disabled?: boolean
  /** Keep the menu open after selecting (e.g. toggling several view options). */
  keepOpen?: boolean
}

export interface MenuSection {
  id: string
  label?: string
  items: readonly MenuItem[]
}

interface MenuProps {
  /** Accessible name of the menu (and of the trigger when it has no visible text). */
  label: string
  /** Built only while open, so expensive item descriptions cost nothing when closed. */
  sections: readonly MenuSection[] | (() => readonly MenuSection[])
  /** Visible content of the trigger button. */
  trigger: ReactNode
  /** The trigger shows only an icon: use `label` as its aria-label and show a tooltip. */
  iconOnly?: boolean
  tooltip?: 'top' | 'bottom'
  triggerClassName?: string
  side?: 'top' | 'bottom'
  align?: 'start' | 'end'
  /** Static content above the items (e.g. "Signed in as …"). */
  header?: ReactNode
  menuClassName?: string
  className?: string
}

/**
 * Menu button (WAI-ARIA APG): Enter/Space/↓ open and focus the first item, ↑/↓/Home/End move,
 * Esc closes and returns focus to the button, Tab closes and moves on, outside press closes.
 */
export function Menu({
  label,
  sections,
  trigger,
  iconOnly = false,
  tooltip,
  triggerClassName,
  side = 'bottom',
  align = 'end',
  header,
  menuClassName,
  className,
}: MenuProps) {
  const [open, setOpen] = useState(false)
  const menuId = useId()
  const rootRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const dismiss = useCallback(() => setOpen(false), [])
  useDismiss(rootRef, open, dismiss)

  useEffect(() => {
    if (open) rootRef.current?.querySelector<HTMLElement>('[role^="menuitem"]:not([aria-disabled])')?.focus()
  }, [open])

  const close = () => {
    setOpen(false)
    buttonRef.current?.focus()
  }

  const onMenuKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const items = [
      ...(rootRef.current?.querySelectorAll<HTMLElement>('[role^="menuitem"]:not([aria-disabled])') ?? []),
    ]
    const i = items.indexOf(document.activeElement as HTMLElement)
    const focusAt = (n: number) => items[(n + items.length) % items.length]?.focus()
    if (e.key === 'Escape') {
      e.preventDefault()
      e.stopPropagation() // inside a dialog, Esc closes the menu, not the dialog
      close()
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      focusAt(i + 1)
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      focusAt(i - 1)
    } else if (e.key === 'Home') {
      e.preventDefault()
      focusAt(0)
    } else if (e.key === 'End') {
      e.preventDefault()
      focusAt(items.length - 1)
    } else if (e.key === 'Tab') {
      setOpen(false)
    }
  }

  const resolved = open ? (typeof sections === 'function' ? sections() : sections) : []

  return (
    <div ref={rootRef} className={cn('relative', className)}>
      <button
        ref={buttonRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        aria-label={iconOnly ? label : undefined}
        onClick={() => setOpen((o) => !o)}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown' && !open) {
            e.preventDefault()
            setOpen(true)
          }
        }}
        className={cn('group/ib relative', triggerClassName)}
      >
        {trigger}
        {tooltip && !open && <Tooltip side={tooltip}>{label}</Tooltip>}
      </button>
      {open && (
        <div
          id={menuId}
          role="menu"
          tabIndex={-1}
          aria-label={label}
          onKeyDown={onMenuKey}
          className={cn(
            'absolute z-50 w-64 max-w-[calc(100vw-1.5rem)] animate-[pop-in_150ms_ease-out] rounded-xl border border-ivory-300 bg-ivory-50 p-1.5 text-charcoal-700 shadow-pop',
            side === 'bottom' ? 'top-full mt-2' : 'bottom-full mb-2',
            align === 'end' ? 'right-0' : 'left-0',
            menuClassName,
          )}
        >
          {header}
          {resolved.map((section, si) => (
            <div
              key={section.id}
              role="group"
              aria-label={section.label}
              className={cn(si > 0 && 'mt-1 border-t border-ivory-300 pt-1')}
            >
              {section.label && (
                <p
                  aria-hidden
                  className="px-2.5 pt-1.5 pb-1 text-[0.6875rem] font-semibold tracking-[0.14em] text-charcoal-500 uppercase"
                >
                  {section.label}
                </p>
              )}
              {section.items.map((item) => (
                <MenuItemButton
                  key={item.id}
                  item={item}
                  onActivate={() => {
                    item.onSelect()
                    if (!item.keepOpen) close()
                  }}
                />
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function MenuItemButton({ item, onActivate }: { item: MenuItem; onActivate: () => void }) {
  const kind = item.kind ?? 'item'
  const role = kind === 'radio' ? 'menuitemradio' : kind === 'checkbox' ? 'menuitemcheckbox' : 'menuitem'
  return (
    <button
      type="button"
      role={role}
      aria-checked={kind === 'item' ? undefined : Boolean(item.checked)}
      aria-disabled={item.disabled || undefined}
      tabIndex={-1}
      onClick={() => !item.disabled && onActivate()}
      className={cn(
        'flex w-full items-start gap-2.5 rounded-lg px-2.5 py-2 text-left text-[0.8125rem] transition-colors',
        'hover:bg-ivory-200 focus:bg-ivory-200 focus:outline-none aria-disabled:cursor-not-allowed aria-disabled:opacity-50',
        item.danger ? 'text-danger-600' : 'text-charcoal-900',
      )}
    >
      {item.icon && (
        <span
          aria-hidden
          className={cn(
            'mt-px flex shrink-0 [&>svg]:size-4',
            item.danger ? 'text-danger-600' : 'text-charcoal-500',
          )}
        >
          {item.icon}
        </span>
      )}
      <span className="min-w-0 flex-1">
        <span className="block font-medium">{item.label}</span>
        {item.description && (
          <span className="mt-0.5 block text-xs leading-snug text-charcoal-500">{item.description}</span>
        )}
      </span>
      {kind !== 'item' && (
        <Check
          aria-hidden
          className={cn('mt-0.5 size-4 shrink-0 text-brand-600', !item.checked && 'invisible')}
        />
      )}
    </button>
  )
}

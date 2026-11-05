import { Bookmark, ChevronDown, LogOut, UserRound } from 'lucide-react'
import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { Logo } from '@/components/brand/Logo'
import { ROUTES } from '@/config/routes'
import { cn } from '@/lib/cn'
import { tokenStorage } from '@/services/tokenStorage'

/** Logo · "Memory Wall Planner" · Profile menu. Sticky, slightly translucent. */
export function PlannerHeader({ onOpenSaved }: { onOpenSaved: () => void }) {
  return (
    <header className="sticky top-0 z-30 border-b border-cream-300 bg-cream-50/90 backdrop-blur">
      <div className="mx-auto flex max-w-[100rem] items-center gap-3 px-4 py-2.5 sm:gap-5 sm:px-6 lg:px-8">
        <Logo className="w-28 shrink-0 sm:w-40" />
        <span aria-hidden className="hidden h-10 w-px bg-cream-400 sm:block" />
        <div className="min-w-0 flex-1">
          <h1 className="truncate font-display text-lg font-semibold text-ink-900 sm:text-2xl">
            Memory Wall Planner
          </h1>
          <p className="hidden truncate text-sm tracking-wide text-ink-500 sm:block">
            Design a wall full of memories.
          </p>
        </div>
        <ProfileMenu onOpenSaved={onOpenSaved} />
      </div>
    </header>
  )
}

/** Menu button pattern: Esc / outside click close, arrow keys move between items. */
function ProfileMenu({ onOpenSaved }: { onOpenSaved: () => void }) {
  const [open, setOpen] = useState(false)
  const menuId = useId()
  const rootRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (!open) return
    const onDown = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('pointerdown', onDown)
    rootRef.current?.querySelector<HTMLElement>('[role="menuitem"]')?.focus()
    return () => document.removeEventListener('pointerdown', onDown)
  }, [open])

  const close = () => {
    setOpen(false)
    buttonRef.current?.focus()
  }

  const onMenuKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const items = [...(rootRef.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? [])]
    const i = items.indexOf(document.activeElement as HTMLElement)
    if (e.key === 'Escape') {
      e.preventDefault()
      close()
    } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      const next = (i + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length
      items[next]?.focus()
    } else if (e.key === 'Tab') {
      setOpen(false)
    }
  }

  const item =
    'flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm text-ink-700 hover:bg-cream-200 focus:bg-cream-200 focus:outline-none [&>svg]:size-4 [&>svg]:text-brand-600'

  return (
    <div ref={rootRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 rounded-full border border-cream-300 bg-white py-1 pr-2 pl-1 shadow-field transition-colors hover:border-cream-400 sm:pr-3"
      >
        <span className="grid size-8 place-items-center rounded-full bg-ink-700 text-cream-50">
          <UserRound aria-hidden className="size-4.5" />
        </span>
        <span className="hidden text-sm font-semibold text-ink-900 sm:inline">Profile</span>
        <ChevronDown
          aria-hidden
          className={cn('size-4 text-ink-500 transition-transform', open && 'rotate-180')}
        />
        <span className="sr-only sm:hidden">Profile</span>
      </button>
      {open && (
        <div
          id={menuId}
          role="menu"
          tabIndex={-1}
          aria-label="Profile"
          onKeyDown={onMenuKey}
          className="absolute top-full right-0 z-50 mt-2 w-60 animate-[toast-in_160ms_ease-out] rounded-xl border border-cream-300 bg-cream-50 p-1.5 shadow-2xl"
        >
          <p className="px-3 pt-2 pb-2.5 text-xs text-ink-500">
            Signed in · <span className="font-medium text-ink-700">Preview account</span>
          </p>
          <button
            type="button"
            role="menuitem"
            className={item}
            onClick={() => {
              setOpen(false)
              onOpenSaved()
            }}
          >
            <Bookmark aria-hidden /> My Saved Templates
          </button>
          <button
            type="button"
            role="menuitem"
            className={item}
            onClick={() => {
              // Local sign-out now; Phase 5 also calls POST /auth/logout first.
              tokenStorage.clear()
              navigate(ROUTES.login, { replace: true })
            }}
          >
            <LogOut aria-hidden /> Sign out
          </button>
        </div>
      )}
    </div>
  )
}

import { X } from 'lucide-react'
import { useEffect, useId, useRef, type ReactNode } from 'react'
import { cn } from '@/lib/cn'
import { IconButton } from './IconButton'

type DialogSize = 'sm' | 'md' | 'lg' | 'full'

const sizes: Record<DialogSize, string> = {
  sm: 'w-[min(100%-2rem,28rem)]',
  md: 'w-[min(100%-2rem,40rem)]',
  lg: 'w-[min(100%-2rem,68rem)] max-h-[min(100dvh-2rem,56rem)]',
  full: 'h-[calc(100dvh-1rem)] w-[calc(100%-1rem)] max-h-none max-w-none sm:h-[calc(100dvh-2rem)] sm:w-[calc(100%-2rem)]',
}

interface DialogProps {
  open: boolean
  onClose: () => void
  title: ReactNode
  description?: ReactNode
  size?: DialogSize
  /** Extra controls in the header, before the close button. */
  headerActions?: ReactNode
  /** Sticky footer (buttons). */
  footer?: ReactNode
  children: ReactNode
  className?: string
  bodyClassName?: string
}

/**
 * Modal built on the native <dialog> (showModal): focus is trapped and returned to the trigger,
 * the page behind is inert, and Esc closes it, all handled by the browser.
 * Children only render while open, so heavy content costs nothing when closed.
 */
export function Dialog({
  open,
  onClose,
  title,
  description,
  size = 'md',
  headerActions,
  footer,
  children,
  className,
  bodyClassName,
}: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  const descId = useId()

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) {
      dialog.showModal()
      // showModal() focuses the first focusable element (the Close button). Honour an explicit
      // initial-focus target instead, e.g. the name field in "Save design".
      const target = dialog.querySelector<HTMLElement>('[data-autofocus]')
      if (target) {
        target.focus()
        if (target instanceof HTMLInputElement) target.select()
      }
    }
    if (!open && dialog.open) dialog.close()
  }, [open])

  // Backdrop click closes (mouse/touch convenience; keyboard users have Esc and the Close button).
  const onCloseRef = useRef(onClose)
  useEffect(() => {
    onCloseRef.current = onClose
  })
  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    // Both ends must be on the backdrop: selecting text in a field and releasing outside the
    // panel also produces a click whose target is the <dialog>, and must not close it.
    const press = { onBackdrop: false }
    const onPointerDown = (e: PointerEvent) => {
      press.onBackdrop = e.target === dialog
    }
    const onClick = (e: MouseEvent) => {
      if (press.onBackdrop && e.target === dialog) onCloseRef.current()
      press.onBackdrop = false
    }
    dialog.addEventListener('pointerdown', onPointerDown)
    dialog.addEventListener('click', onClick)
    return () => {
      dialog.removeEventListener('pointerdown', onPointerDown)
      dialog.removeEventListener('click', onClick)
    }
  }, [])

  // Lock page scroll while open (dialogs don't do this natively).
  useEffect(() => {
    if (!open) return
    const root = document.documentElement
    const previous = root.style.overflow
    root.style.overflow = 'hidden'
    return () => {
      root.style.overflow = previous
    }
  }, [open])

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      aria-describedby={description ? descId : undefined}
      onCancel={(e) => {
        e.preventDefault() // Esc → let React state drive closing
        onClose()
      }}
      className={cn(
        'm-auto flex-col overflow-hidden rounded-2xl border border-ivory-300 bg-ivory-50 p-0 text-charcoal-700 shadow-2xl open:flex',
        'backdrop:bg-charcoal-900/60 backdrop:backdrop-blur-[3px]',
        'open:animate-[dialog-in_220ms_cubic-bezier(0.2,0.9,0.3,1)] open:backdrop:animate-[fade-in_200ms_ease-out]',
        sizes[size],
        className,
      )}
    >
      {open && (
        <>
          <header className="flex items-center gap-3 border-b border-ivory-300 px-4 py-3 sm:px-6 sm:py-3.5">
            <div className="min-w-0 flex-1">
              <h2 id={titleId} className="truncate text-lg font-semibold text-charcoal-900 sm:text-xl">
                {title}
              </h2>
              {description && (
                <p id={descId} className="mt-0.5 truncate text-[0.8125rem] text-charcoal-500">
                  {description}
                </p>
              )}
            </div>
            <div className="flex shrink-0 items-center gap-1.5">
              {headerActions}
              <IconButton label="Close" icon={<X />} variant="quiet" size="sm" onClick={onClose} />
            </div>
          </header>
          <div
            className={cn(
              'min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 py-4 sm:px-6 sm:py-5',
              bodyClassName,
            )}
          >
            {children}
          </div>
          {footer && (
            <footer className="flex flex-wrap items-center justify-end gap-2 border-t border-ivory-300 bg-ivory-100/60 px-4 py-3 sm:px-6">
              {footer}
            </footer>
          )}
        </>
      )}
    </dialog>
  )
}

import { useId, type InputHTMLAttributes, type ReactNode, type Ref } from 'react'
import { cn } from '@/lib/cn'

export interface TextFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'size'> {
  label: ReactNode
  /** Decorative icon inside the field, left side. Rendered aria-hidden. */
  leftIcon?: ReactNode
  /** Content inside the field, right side (e.g. a show/hide password button). */
  rightSlot?: ReactNode
  /** Fixed content inside the field, left of the input (e.g. "+91" country code). */
  startAddon?: ReactNode
  error?: string
  hint?: ReactNode
  /** Classes for the outer wrapper (label + field + message). */
  className?: string
  /** Classes for the <input> itself. */
  inputClassName?: string
  ref?: Ref<HTMLInputElement>
}

/**
 * Labelled text input matching the auth designs: 48px tall, cream surface, optional icon/addon
 * on the left and an action slot on the right. Error and hint are wired via aria-describedby.
 *
 * Sizes read optional CSS custom properties (--field-h, --field-label-*, --field-input-size,
 * --field-hint-*) so a page can set its density (the auth pages do, see `.auth-scope` in
 * index.css). Without them the field renders at the default sizes.
 */
export function TextField({
  label,
  leftIcon,
  rightSlot,
  startAddon,
  error,
  hint,
  id,
  className,
  inputClassName,
  'aria-describedby': ariaDescribedBy,
  ...inputProps
}: TextFieldProps) {
  const autoId = useId()
  const inputId = id ?? autoId
  const hintId = hint ? `${inputId}-hint` : undefined
  const errorId = error ? `${inputId}-error` : undefined
  // Merge, never replace: a caller's describedby must not drop the error/hint association.
  const describedBy = [errorId, hintId, ariaDescribedBy].filter(Boolean).join(' ') || undefined

  return (
    <div className={cn('flex flex-col gap-[var(--field-label-gap,0.5rem)]', className)}>
      <label
        htmlFor={inputId}
        className="text-[length:var(--field-label-size,0.875rem)] leading-[var(--field-label-leading,1.25rem)] font-semibold text-ink-900"
      >
        {label}
      </label>

      <div
        className={cn(
          'group flex h-[var(--field-h,3rem)] items-center gap-3 rounded-field border bg-cream-50 px-3.5 shadow-field',
          'transition-[border-color,box-shadow] duration-150',
          'focus-within:border-brand-600 focus-within:ring-3 focus-within:ring-brand-600/15',
          // Windows High Contrast drops box-shadow rings; give it a real outline in the system colour.
          'forced-colors:focus-within:outline-2 forced-colors:focus-within:outline-offset-2 forced-colors:focus-within:outline-[Highlight]',
          error ? 'border-danger-600' : 'border-cream-600/70 hover:border-cream-600',
          inputProps.disabled && 'opacity-60',
        )}
      >
        {leftIcon && (
          <span
            aria-hidden
            className="flex shrink-0 text-ink-500 transition-colors group-focus-within:text-brand-600 [&>svg]:size-5"
          >
            {leftIcon}
          </span>
        )}
        {startAddon && (
          <span className="flex shrink-0 items-center self-stretch border-r border-cream-300 pr-3 text-[length:var(--field-input-size,1rem)] font-semibold text-brand-700">
            {startAddon}
          </span>
        )}

        <input
          {...inputProps}
          id={inputId}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={cn(
            // 16px by default: keeps iOS Safari from zooming on focus. Pages may lower it only for
            // fine pointers (the auth scope forces 16px back under `pointer: coarse`).
            'h-full min-w-0 flex-1 bg-transparent text-[length:var(--field-input-size,1rem)] leading-normal text-ink-900 outline-none placeholder:text-ink-500',
            'focus-visible:outline-none',
            inputClassName,
          )}
        />

        {rightSlot && <span className="flex shrink-0 items-center">{rightSlot}</span>}
      </div>

      {error && (
        <p
          id={errorId}
          className="text-[length:var(--field-hint-size,0.875rem)] leading-[var(--field-hint-leading,1.25rem)] break-words text-danger-600"
        >
          {error}
        </p>
      )}
      {hint && !error && (
        <p
          id={hintId}
          className="text-[length:var(--field-hint-size,0.875rem)] leading-[var(--field-hint-leading,1.25rem)] text-ink-500"
        >
          {hint}
        </p>
      )}
    </div>
  )
}

import type { ReactNode } from 'react'
import { EstablishedTag } from '@/components/brand/EstablishedTag'
import { Logo } from '@/components/brand/Logo'
import { cn } from '@/lib/cn'

interface AuthHeaderProps {
  title: ReactNode
  subtitle?: ReactNode
  /** Login's heading is left-aligned with the form; Register's is centred. */
  align?: 'left' | 'center'
  /** Login's title is dark ink; Register's is brand crimson (per the mockups). */
  titleTone?: 'ink' | 'brand'
  /**
   * Tighter header for longer forms (Register): smaller logo and spacing, and a fluid title that
   * stays on one line in the 448px form column from 320px phones up.
   */
  compact?: boolean
}

/**
 * Logo, "— EST. 1985 —" and the page heading (the page's only <h1>). The classes without a
 * variant are the full-size design. `auth-fluid:` sizes come from `.auth-scope` (index.css) and
 * follow the viewport height.
 */
export function AuthHeader({
  title,
  subtitle,
  align = 'left',
  titleTone = 'ink',
  compact = false,
}: AuthHeaderProps) {
  return (
    <header className="flex flex-col">
      <div
        className={cn(
          'flex flex-col items-center auth-fluid:gap-[var(--auth-brand-gap)]',
          compact ? 'gap-2' : 'gap-3',
        )}
      >
        <Logo
          className={cn(
            compact ? 'w-40 sm:w-48' : 'w-44 sm:w-56 hero-fits:w-60',
            'auth-fluid:w-[var(--auth-logo-w)]',
          )}
        />
        <EstablishedTag className="auth-fluid:text-[length:var(--auth-est-size)] auth-fluid:leading-4" />
      </div>

      <div
        className={cn(
          'flex flex-col gap-2 auth-fluid:gap-[var(--auth-title-gap)]',
          compact ? 'mt-6' : 'mt-8',
          'auth-fluid:mt-[var(--auth-header-gap)]',
          align === 'center' && 'items-center text-center',
        )}
      >
        <h1
          className={cn(
            'font-semibold tracking-tight text-balance',
            compact ? 'text-[clamp(1.75rem,8.5vw,2.5rem)]' : 'text-[2.5rem] sm:text-5xl',
            'auth-fluid:text-[length:var(--auth-title-size)]',
            // Must come AFTER the font-size classes: tailwind-merge drops a `leading-*` that
            // precedes a font-size utility (font-size resets line-height).
            'leading-[1.1]',
            titleTone === 'brand' && 'text-brand-700',
          )}
        >
          {title}
        </h1>
        {subtitle && (
          <p
            className={cn(
              'text-pretty text-ink-500',
              compact ? 'text-base' : 'text-base sm:text-lg',
              'auth-fluid:text-[length:var(--auth-subtitle-size)] auth-fluid:leading-[1.4]',
              // Centred subtitles may use the column's side padding (as in the Register mockup),
              // so one-line copy doesn't wrap inside the 448px form width.
              align === 'center' && 'sm:-mx-6 sm:self-stretch',
            )}
          >
            {subtitle}
          </p>
        )}
      </div>
    </header>
  )
}

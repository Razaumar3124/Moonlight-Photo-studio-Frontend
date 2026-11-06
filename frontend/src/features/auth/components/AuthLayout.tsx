import type { ReactNode } from 'react'
import type { HeroImageAsset } from '@/assets/types'
import { MEDIA } from '@/config/media'
import { useMediaQuery } from '@/hooks/useMediaQuery'
import { cn } from '@/lib/cn'
import { useViewportFitCover } from '../hooks/useViewportFitCover'
import { AuthDecorations, type AuthVariant } from './AuthDecorations'
import { AuthHero } from './AuthHero'

interface AuthLayoutProps {
  hero: HeroImageAsset
  variant: AuthVariant
  /** Denser layout for longer forms (Register): wider column, tighter rhythm. */
  compact?: boolean
  children: ReactNode
}

/**
 * Shared shell for Login / Register (docs/RESPONSIVE.md):
 * - default: single column, form centred on cream with corner ornaments (mobile mockups);
 * - `hero-fits` (≥ lg, landscape ≥ 4:3): photo left (~56%), form panel right (≥ 30rem).
 *
 * `<main class="auth-scope">` carries the height-aware density (index.css). On `auth-fluid`
 * viewports (≤ 880px tall, or phones) the column's width and padding come from those properties;
 * taller viewports keep the full-size classes below. The column only has a min-height, so it
 * still scrolls when content can't fit (keyboard, zoom, large fonts, validation errors).
 */
export function AuthLayout({ hero, variant, compact = false, children }: AuthLayoutProps) {
  const showHero = useMediaQuery(MEDIA.heroFits)
  useViewportFitCover()

  return (
    <div className="min-h-dvh bg-cream-100 hero-fits:grid hero-fits:grid-cols-[minmax(0,1fr)_minmax(30rem,44%)]">
      {showHero && <AuthHero image={hero} />}

      <main
        data-density={compact ? 'compact' : undefined}
        className="auth-scope relative isolate flex min-h-dvh flex-col overflow-hidden bg-linear-to-b from-cream-50 to-cream-100"
      >
        <AuthDecorations variant={variant} />
        {/*
          Bottom padding keeps the footer link clear of the corner wave. It must be ≥ the wave's
          height where the footer text ends (checked at 320–2560px, see AuthDecorations sizes).
          Side padding respects notches in landscape (viewport-fit=cover, useViewportFitCover).
        */}
        <div
          className={cn(
            'mx-auto flex w-full max-w-md flex-1 flex-col justify-center pt-10 pb-24 sm:pt-14 sm:pb-28 hero-fits:pb-16',
            'px-[max(1rem,env(safe-area-inset-left),env(safe-area-inset-right))]',
            'sm:px-[max(1.5rem,env(safe-area-inset-left),env(safe-area-inset-right))]',
            // On hero-fits the wave sits ≥ 130px right of the footer text, so 24px is enough.
            // Register's mockup form is ~8% wider than login's (489 vs 451px at mockup scale).
            compact && 'max-w-[30rem] sm:pt-10 hero-fits:pt-6 hero-fits:pb-6',
            'auth-fluid:max-w-[var(--auth-col-w)] auth-fluid:pt-[var(--auth-pad-t)] auth-fluid:pb-[var(--auth-pad-b)]',
          )}
        >
          {children}
        </div>
      </main>
    </div>
  )
}

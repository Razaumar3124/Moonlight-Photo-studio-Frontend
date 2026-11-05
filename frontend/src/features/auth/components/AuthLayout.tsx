import type { ReactNode } from 'react'
import type { HeroImageAsset } from '@/assets/types'
import { MEDIA } from '@/config/media'
import { useMediaQuery } from '@/hooks/useMediaQuery'
import { cn } from '@/lib/cn'
import { AuthDecorations, type AuthVariant } from './AuthDecorations'
import { AuthHero } from './AuthHero'

interface AuthLayoutProps {
  hero: HeroImageAsset
  variant: AuthVariant
  /** Less vertical padding on wide layouts, for longer forms (Register). */
  compact?: boolean
  children: ReactNode
}

/**
 * Shared shell for Login / Register (docs/RESPONSIVE.md):
 * - default: single column, form centred on cream with corner ornaments (mobile mockups);
 * - `hero-fits` (≥ lg, landscape ≥ 4:3): photo left (~56%), form panel right (≥ 30rem).
 */
export function AuthLayout({ hero, variant, compact = false, children }: AuthLayoutProps) {
  const showHero = useMediaQuery(MEDIA.heroFits)

  return (
    <div className="min-h-dvh bg-cream-100 hero-fits:grid hero-fits:grid-cols-[minmax(0,1fr)_minmax(30rem,44%)]">
      {showHero && <AuthHero image={hero} />}

      <main className="relative isolate flex min-h-dvh flex-col overflow-hidden bg-linear-to-b from-cream-50 to-cream-100">
        <AuthDecorations variant={variant} />
        {/*
          Bottom padding keeps the footer link clear of the corner wave. It must be ≥ the wave's
          height where the footer text ends (checked at 320–1440px, see AuthDecorations sizes).
        */}
        <div
          className={cn(
            'mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-4 pt-10 pb-24 sm:px-6 sm:pt-14 sm:pb-28 hero-fits:pb-16 short:pt-4 short:pb-20',
            // On hero-fits (non-short) the wave sits ≥ 130px right of the footer text, so 24px is enough.
            // Register's mockup form is ~8% wider than login's (489 vs 451px at mockup scale).
            compact && 'max-w-[30rem] sm:pt-10 hero-fits:pt-6 hero-fits:pb-6',
          )}
        >
          {children}
        </div>
      </main>
    </div>
  )
}

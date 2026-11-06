import { authAssets } from '@/assets/auth'
import type { ImageAsset } from '@/assets/types'
import { cn } from '@/lib/cn'

export type AuthVariant = 'login' | 'register'

interface Placement {
  asset: ImageAsset
  className: string
}

const d = authAssets.decorations

/**
 * Corner ornaments per screen, positioned to match the mockups at every width. On `auth-fluid`
 * viewports (≤ 880px tall, or phones) they scale with the height via the `--auth-*` widths in
 * index.css, so short screens don't need extra padding to keep the footer clear of the wave.
 */
const PLACEMENTS: Record<AuthVariant, Placement[]> = {
  login: [
    {
      asset: d.leafTopRight,
      className: 'top-0 right-0 w-24 sm:w-32 hero-fits:w-36 3xl:w-48 auth-fluid:w-[var(--auth-leaf-tr)]',
    },
    {
      asset: d.leafBottomCenter,
      className: 'bottom-2 left-0 w-14 sm:w-20 hero-fits:w-16 3xl:w-24 auth-fluid:w-[var(--auth-leaf-bc)]',
    },
    // W3: the login wave is unusable, so login shares the register wave.
    // Sizes are capped so the footer link never overlaps it (see AuthLayout bottom padding).
    {
      asset: d.waveRedBottomRight,
      className: 'right-0 bottom-0 w-36 sm:w-44 hero-fits:w-44 3xl:w-60 auth-fluid:w-[var(--auth-wave-br)]',
    },
  ],
  register: [
    {
      asset: d.leafTopLeft,
      className: 'top-0 left-0 w-36 opacity-80 sm:w-56 3xl:w-72 auth-fluid:w-[var(--auth-leaf-tl)]',
    },
    // Kept narrow on phones so it never touches the centred logo (logo spans ~50% of 320px).
    {
      asset: d.waveRedTopRight,
      className:
        'top-0 right-0 w-16 min-[360px]:w-20 sm:w-36 hero-fits:w-40 3xl:w-56 auth-fluid:w-[var(--auth-wave-tr)]',
    },
    {
      asset: d.waveSubtleBottomLeft,
      className: 'bottom-0 left-0 w-56 opacity-80 sm:w-80 3xl:w-96 auth-fluid:w-[var(--auth-wave-bl)]',
    },
    // Same sizing rules as login, so the footer link never overlaps (AuthLayout bottom padding).
    {
      asset: d.waveRedBottomRight,
      className: 'right-0 bottom-0 w-36 sm:w-44 hero-fits:w-44 3xl:w-60 auth-fluid:w-[var(--auth-wave-br)]',
    },
  ],
}

/** Purely decorative layer behind the auth form. Hidden from assistive tech and pointer events. */
export function AuthDecorations({ variant }: { variant: AuthVariant }) {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 -z-10 overflow-hidden select-none">
      {PLACEMENTS[variant].map(({ asset, className }) => (
        <img
          key={asset.src + className}
          src={asset.src}
          width={asset.width}
          height={asset.height}
          alt=""
          decoding="async"
          draggable={false}
          className={cn('absolute h-auto max-w-none', className)}
        />
      ))}
    </div>
  )
}

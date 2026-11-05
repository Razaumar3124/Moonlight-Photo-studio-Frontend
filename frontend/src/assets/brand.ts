import googleGSrc from './icons/google-g.svg'
import logoSrc from './images/logo.svg'
import type { ImageAsset } from './types'

export const brandAssets = {
  /** Horizontal lockup (crescent + MOONLIGHT / PHOTO STUDIO). Traced from raster, see ASSETS.md W1. */
  logo: { src: logoSrc, width: 353, height: 132, alt: 'Moonlight Photo Studio' },
} as const satisfies Record<string, ImageAsset>

export const iconAssets = {
  google: { src: googleGSrc, width: 48, height: 48, alt: '' },
} as const satisfies Record<string, ImageAsset>

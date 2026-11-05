import loginLeafBottomSrc from './images/login/leaf-bottom-center.svg'
import loginLeafTopRightSrc from './images/login/leaf-top-right.svg'
import loginHeroSrc from './images/login/background-frames.webp?w=928&quality=80&format=webp'
import loginHeroSrcSet from './images/login/background-frames.webp?w=480;720;928&format=webp&quality=80&as=srcset'
import registerHeroSrc from './images/register/background-living-room.webp?w=935&quality=80&format=webp'
import registerHeroSrcSet from './images/register/background-living-room.webp?w=480;720;935&format=webp&quality=80&as=srcset'
import registerLeafTopLeftSrc from './images/register/leaf-top-left.svg'
import waveRedBottomRightSrc from './images/register/wave-red-bottom-right.svg'
import waveRedTopRightSrc from './images/register/wave-red-top-right.svg'
import waveSubtleBottomLeftSrc from './images/register/wave-subtle-bottom-left.svg'
import type { HeroImageAsset, ImageAsset } from './types'

/**
 * NOTE: both hero photos have their tagline text baked into the image (ASSETS.md W2).
 * - Don't overlay the same text in HTML; the tagline is in `alt` for screen readers.
 * - Render with `object-cover` + `objectPosition`, and only under the `hero-fits` variant
 *   (lg + landscape ≥ 4:3, defined in index.css). Narrower panels would crop the text.
 */
export const authAssets = {
  login: {
    hero: {
      src: loginHeroSrc,
      srcSet: loginHeroSrcSet,
      width: 928,
      height: 941,
      // Tagline spans x 24–66%. 40% keeps it whole down to a 0.5:1 panel.
      objectPosition: '40% 40%',
      alt: 'Every picture tells a story. Preserve your most beautiful moments with Moonlight Photo Studio.',
    } satisfies HeroImageAsset,
  },
  register: {
    hero: {
      src: registerHeroSrc,
      srcSet: registerHeroSrcSet,
      width: 935,
      height: 937,
      // Tagline spans x 24–89%. 75% keeps it whole down to a ~0.66:1 panel.
      objectPosition: '75% 40%',
      alt: 'Your memories deserve a beautiful home. Create an account and start turning your favourite moments into timeless keepsakes.',
    } satisfies HeroImageAsset,
  },
  /** Decorative ornaments: always render with alt="" and aria-hidden. */
  decorations: {
    leafTopRight: { src: loginLeafTopRightSrc, width: 133, height: 133, alt: '' },
    leafBottomCenter: { src: loginLeafBottomSrc, width: 88, height: 121, alt: '' },
    leafTopLeft: { src: registerLeafTopLeftSrc, width: 237, height: 191, alt: '' },
    waveRedTopRight: { src: waveRedTopRightSrc, width: 210, height: 181, alt: '' },
    /**
     * Used on BOTH login and register. login/wave-red-bottom-right.svg is unusable: its trace
     * contains a fragment of the "Create an account" link text (ASSETS.md W3).
     */
    waveRedBottomRight: { src: waveRedBottomRightSrc, width: 164, height: 142, alt: '' },
    waveSubtleBottomLeft: { src: waveSubtleBottomLeftSrc, width: 384, height: 151, alt: '' },
  } satisfies Record<string, ImageAsset>,
} as const

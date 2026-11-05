import type { HeroImageAsset } from '@/assets/types'

interface AuthHeroProps {
  image: HeroImageAsset
}

/**
 * Left-hand photo panel. The tagline is baked into the image (ASSETS.md W2), so the alt text
 * carries it and nothing is overlaid. The parent mounts this only under `hero-fits`, so devices
 * that don't show it never download it.
 */
export function AuthHero({ image }: AuthHeroProps) {
  return (
    <div className="sticky top-0 h-dvh overflow-hidden bg-cream-200">
      <img
        src={image.src}
        srcSet={image.srcSet}
        // The panel is ~56% of the viewport width; height usually drives the crop, and the
        // largest candidate is the full-resolution source anyway.
        sizes="56vw"
        width={image.width}
        height={image.height}
        alt={image.alt}
        fetchPriority="high"
        decoding="async"
        draggable={false}
        className="size-full object-cover select-none"
        style={{ objectPosition: image.objectPosition }}
      />
    </div>
  )
}

/**
 * Asset manifests: one module per area so each page bundles only the assets it uses.
 *   @/assets/brand       → logo, shared icons
 *   @/assets/auth        → login / register heroes and ornaments
 *   @/assets/memoryWall  → planner backdrop, sample photos, layout thumbnails
 * These modules are the ONLY importers of image files. Components never import raw paths.
 * Inventory, quality notes and workarounds: docs/ASSETS.md.
 */

export interface ImageAsset {
  /** Fallback / default URL. */
  src: string
  /** Responsive candidates for `srcSet` (raster only). */
  srcSet?: string
  /** Intrinsic size. Always pass to <img> to prevent layout shift. */
  width: number
  height: number
  /** Default alt text. Use `''` for purely decorative images. */
  alt: string
}

/** A photo with text baked in: `objectPosition` is the crop anchor that keeps the text in view. */
export interface HeroImageAsset extends ImageAsset {
  objectPosition: string
}

export type Orientation = 'portrait' | 'landscape'

export interface SamplePhotoAsset extends ImageAsset {
  id: string
  orientation: Orientation
}

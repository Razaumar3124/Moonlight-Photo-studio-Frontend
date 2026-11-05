import roomBackgroundSrc from './images/memory_wall/background-wall-plain.webp?w=1466&quality=80&format=webp'
import roomBackgroundSrcSet from './images/memory_wall/background-wall-plain.webp?w=640;960;1466&format=webp&quality=80&as=srcset'
import layoutBalancedGridSrc from './images/memory_wall/layouts/ai-balanced-grid.webp'
import layoutCentreFocusSrc from './images/memory_wall/layouts/ai-centre-focus.webp'
import layoutCreativeSalonSrc from './images/memory_wall/layouts/ai-creative-salon.webp'
import layoutMinimalRowSrc from './images/memory_wall/layouts/ai-minimal-row.webp'
import type { SamplePhotoAsset } from './types'

const SAMPLE_PHOTO_GLOB = import.meta.glob<string>('./images/memory_wall/frames/*.{webp,png}', {
  eager: true,
  import: 'default',
  // PNG sources are ~2.4 MB each; this re-encodes every sample to ≤640px WebP.
  query: '?w=320;640&format=webp&quality=78&as=srcset',
})
const SAMPLE_PHOTO_SRC_GLOB = import.meta.glob<string>('./images/memory_wall/frames/*.{webp,png}', {
  eager: true,
  import: 'default',
  query: '?w=640&format=webp&quality=78',
})

const SAMPLE_PHOTO_META: ReadonlyArray<Omit<SamplePhotoAsset, 'src' | 'srcSet'> & { file: string }> = [
  {
    id: 'frame-01',
    file: 'frame-01.webp',
    width: 768,
    height: 1024,
    orientation: 'portrait',
    alt: 'Smiling family of three on a sofa',
  },
  {
    id: 'frame-02',
    file: 'frame-02.webp',
    width: 768,
    height: 1024,
    orientation: 'portrait',
    alt: 'Couple embracing outdoors',
  },
  {
    id: 'frame-03',
    file: 'frame-03.webp',
    width: 768,
    height: 1024,
    orientation: 'portrait',
    alt: 'Hiker walking a mountain trail',
  },
  {
    id: 'frame-04',
    file: 'frame-04.webp',
    width: 768,
    height: 1024,
    orientation: 'portrait',
    alt: 'Laughing child in a straw hat',
  },
  {
    id: 'frame-05',
    file: 'frame-05.webp',
    width: 768,
    height: 1024,
    orientation: 'portrait',
    alt: 'Friends cheering at sunset',
  },
  {
    id: 'frame-06',
    file: 'frame-06.png',
    width: 1086,
    height: 1448,
    orientation: 'portrait',
    alt: 'Elderly couple smiling together at home',
  },
  {
    id: 'frame-07',
    file: 'frame-07.png',
    width: 1086,
    height: 1448,
    orientation: 'portrait',
    alt: 'Family walking on a beach at sunset',
  },
  {
    id: 'frame-08',
    file: 'frame-08.png',
    width: 1448,
    height: 1086,
    orientation: 'landscape',
    alt: 'Hiker on a ridge at sunrise above the clouds',
  },
  {
    id: 'frame-09',
    file: 'frame-09.png',
    width: 1086,
    height: 1448,
    orientation: 'portrait',
    alt: 'Mother and daughter sharing a hug',
  },
  {
    id: 'frame-10',
    file: 'frame-10.png',
    width: 1086,
    height: 1448,
    orientation: 'portrait',
    alt: 'Couple in front of a historic monument',
  },
]

/** Bundled sample photos for "Fill empty frames with samples" and demo layouts. */
export const samplePhotos: readonly SamplePhotoAsset[] = SAMPLE_PHOTO_META.map(({ file, ...meta }) => {
  const key = `./images/memory_wall/frames/${file}`
  const src = SAMPLE_PHOTO_SRC_GLOB[key]
  const srcSet = SAMPLE_PHOTO_GLOB[key]
  if (!src || !srcSet) throw new Error(`Sample photo missing from assets: ${file}`)
  return { ...meta, src, srcSet }
})

export const memoryWallAssets = {
  /**
   * Room photo with a sofa baked in (1466×667, ~2.2:1). Use as the "room" backdrop only;
   * the paintable wall itself is drawn in CSS. See ASSETS.md → workaround W4.
   */
  roomBackground: {
    src: roomBackgroundSrc,
    srcSet: roomBackgroundSrcSet,
    width: 1466,
    height: 667,
    alt: '',
  },
  /** AI Layout Assistant preset thumbnails (≈349×284, displayed ≤ 120px wide → crisp at 2×). */
  layoutThumbnails: {
    balancedGrid: {
      src: layoutBalancedGridSrc,
      width: 349,
      height: 284,
      alt: 'Balanced grid layout preview',
    },
    creativeSalon: {
      src: layoutCreativeSalonSrc,
      width: 349,
      height: 284,
      alt: 'Creative salon layout preview',
    },
    centreFocus: { src: layoutCentreFocusSrc, width: 349, height: 284, alt: 'Centre focus layout preview' },
    minimalRow: { src: layoutMinimalRowSrc, width: 345, height: 284, alt: 'Minimal row layout preview' },
  },
} as const

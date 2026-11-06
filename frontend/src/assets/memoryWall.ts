// Room layers (ASSETS.md W4): an empty floor + skirting strip, plus transparent cut-outs drawn to
// scale over the painted wall. WebP keeps the cut-outs' alpha.
import floorStripSrc from './images/memory_wall/room-floor-strip.png?w=2508&quality=80&format=webp'
import sofaSrc from './images/memory_wall/sofa-84in.png?w=1600&quality=84&format=webp'
import lampSrc from './images/memory_wall/decor-floor-lamp.png?w=480&quality=84&format=webp'
import plantSrc from './images/memory_wall/decor-plant.png?w=520&quality=84&format=webp'
// AI layout presets: 1448×1086 sources, shown ≤ 160px wide.
import layoutBalancedGridSrc from './images/memory_wall/layouts/ai-balanced-grid.png?w=480&quality=78&format=webp'
import layoutCentreFocusSrc from './images/memory_wall/layouts/ai-centre-focus.png?w=480&quality=78&format=webp'
import layoutCreativeSalonSrc from './images/memory_wall/layouts/ai-creative-salon.png?w=480&quality=78&format=webp'
import layoutMinimalRowSrc from './images/memory_wall/layouts/ai-minimal-row.png?w=480&quality=78&format=webp'
import layoutBalancedGridSet from './images/memory_wall/layouts/ai-balanced-grid.png?w=240;480&format=webp&quality=78&as=srcset'
import layoutCentreFocusSet from './images/memory_wall/layouts/ai-centre-focus.png?w=240;480&format=webp&quality=78&as=srcset'
import layoutCreativeSalonSet from './images/memory_wall/layouts/ai-creative-salon.png?w=240;480&format=webp&quality=78&as=srcset'
import layoutMinimalRowSet from './images/memory_wall/layouts/ai-minimal-row.png?w=240;480&format=webp&quality=78&as=srcset'
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
  query: '?w=640&quality=78&format=webp',
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
  {
    id: 'frame-11',
    file: 'frame-11.png',
    width: 1448,
    height: 1086,
    orientation: 'landscape',
    alt: 'Family flying a kite on a hilltop at sunset',
  },
  {
    id: 'frame-12',
    file: 'frame-12.png',
    width: 1448,
    height: 1086,
    orientation: 'landscape',
    alt: 'Grandparents laughing together on a garden bench',
  },
  {
    id: 'frame-13',
    file: 'frame-13.png',
    width: 1448,
    height: 1086,
    orientation: 'landscape',
    alt: 'Couple walking hand in hand along a beach at sunset',
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
   * Room layers, measured on their sources (pixel boxes are in SOURCE pixels; the bundled files
   * are resized, which SVG scales back). Used by WallSvg and documented in ASSETS.md W4.
   */
  room: {
    /** 2508×627. Skirting top at y=450, floor from y=485: 35px = a 4″ skirting → 8.75 px/in. */
    floorStrip: { src: floorStripSrc, width: 2508, height: 627, alt: '' },
    /** 2146×733, opaque box x24 y27 2088×693 px = the 84″ reference sofa. */
    sofa: { src: sofaSrc, width: 2146, height: 733, alt: '' },
    /** 887×1774, opaque box x203 y33 480×1710 px = a 60″ floor lamp. */
    lamp: { src: lampSrc, width: 887, height: 1774, alt: '' },
    /** 887×1774, opaque box x10 y19 867×1732 px = a 36″ potted plant. */
    plant: { src: plantSrc, width: 887, height: 1774, alt: '' },
  },
  /** AI Layout Assistant preset thumbnails (4:3, displayed ≤ 160px wide → crisp at 3×). */
  layoutThumbnails: {
    balancedGrid: {
      src: layoutBalancedGridSrc,
      srcSet: layoutBalancedGridSet,
      width: 1448,
      height: 1086,
      alt: 'Balanced grid layout preview',
    },
    creativeSalon: {
      src: layoutCreativeSalonSrc,
      srcSet: layoutCreativeSalonSet,
      width: 1448,
      height: 1086,
      alt: 'Creative salon layout preview',
    },
    centreFocus: {
      src: layoutCentreFocusSrc,
      srcSet: layoutCentreFocusSet,
      width: 1448,
      height: 1086,
      alt: 'Centre focus layout preview',
    },
    minimalRow: {
      src: layoutMinimalRowSrc,
      srcSet: layoutMinimalRowSet,
      width: 1448,
      height: 1086,
      alt: 'Minimal row layout preview',
    },
  },
} as const

import type { LayoutStyleId, Orientation } from '../constants'
import type { TemplateSpec } from './plannerState'

/**
 * Layout templates (mock catalogue). Shaped like the planner's TemplateSpec rather than the
 * API's LayoutTemplate: the API describes slots by relative position, while the planner computes
 * positions itself. Phase 5 maps GET /templates → these (API_ALIGNMENT M6/M10).
 */
export interface PlannerTemplate extends TemplateSpec {
  id: string
  name: string
  description: string
}

const many = (count: number, sizeId: string, orientation: Orientation = 'portrait') =>
  Array.from({ length: count }, () => ({ sizeId, orientation }))

export const TEMPLATES: readonly PlannerTemplate[] = [
  {
    id: 'balanced-grid',
    name: 'Balanced Grid',
    description: 'Nine Atelier Classic frames in a calm, even 3 × 3 grid.',
    style: 'grid',
    frames: many(9, '12x16'),
    gapIn: 3,
  },
  {
    id: 'creative-salon',
    name: 'Creative Salon',
    description: 'A relaxed cluster of mixed sizes and orientations, gallery-style.',
    style: 'salon',
    frames: [
      { sizeId: '16x20', orientation: 'landscape' },
      { sizeId: '11x14', orientation: 'portrait' },
      { sizeId: '8x10', orientation: 'portrait' },
      { sizeId: '12x16', orientation: 'portrait' },
      { sizeId: '8x10', orientation: 'landscape' },
      { sizeId: '5x7', orientation: 'portrait' },
      { sizeId: '11x14', orientation: 'landscape' },
      { sizeId: '8x10', orientation: 'portrait' },
      { sizeId: '5x7', orientation: 'landscape' },
      { sizeId: '12x16', orientation: 'portrait' },
      { sizeId: '8x10', orientation: 'portrait' },
    ],
    gapIn: 2.5,
  },
  {
    id: 'centre-focus',
    name: 'Centre Focus',
    description: 'One statement print framed by four smaller companions.',
    style: 'centre',
    frames: [{ sizeId: '20x30', orientation: 'landscape' }, ...many(4, '8x10')],
    gapIn: 3,
  },
  {
    id: 'minimal-row',
    name: 'Minimal Row',
    description: 'Four square-feeling frames on one clean line. Perfect above a sofa.',
    style: 'row',
    frames: many(4, '11x14', 'landscape'),
    gapIn: 4,
  },
  {
    id: 'classic-six',
    name: 'Classic Six',
    description: 'A 3 × 2 grid of 11 × 14 prints. Tidy and timeless.',
    style: 'grid',
    frames: many(6, '11x14'),
    gapIn: 3,
  },
  {
    id: 'triptych',
    name: 'Triptych',
    description: 'Three tall prints that tell one story, left to right.',
    style: 'row',
    frames: many(3, '16x20'),
    gapIn: 3,
  },
  {
    id: 'petite-salon',
    name: 'Petite Salon',
    description: 'Small frames, big charm. Ideal for hallways and stairs.',
    style: 'salon',
    frames: [
      { sizeId: '8x10', orientation: 'portrait' },
      { sizeId: '5x7', orientation: 'landscape' },
      { sizeId: '5x7', orientation: 'portrait' },
      { sizeId: '8x10', orientation: 'landscape' },
      { sizeId: '5x7', orientation: 'portrait' },
      { sizeId: '8x10', orientation: 'portrait' },
      { sizeId: '5x7', orientation: 'landscape' },
    ],
    gapIn: 2,
  },
  {
    id: 'statement-centre',
    name: 'Statement Centre',
    description: 'A large landscape hero with six petite frames on its wings.',
    style: 'centre',
    frames: [{ sizeId: '24x36', orientation: 'landscape' }, ...many(6, '5x7')],
    gapIn: 2.5,
  },
  {
    id: 'panorama-row',
    name: 'Panorama Row',
    description: 'Five landscape prints for long walls and corridors.',
    style: 'row',
    frames: many(5, '8x10', 'landscape'),
    gapIn: 3,
  },
  {
    id: 'grand-quad',
    name: 'Grand Quad',
    description: 'Four large prints in a bold 2 × 2 block.',
    style: 'grid',
    frames: many(4, '16x20'),
    gapIn: 4,
  },
]

export const TEMPLATE_CATEGORIES: ReadonlyArray<{ value: 'all' | LayoutStyleId; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'grid', label: 'Grid' },
  { value: 'salon', label: 'Salon' },
  { value: 'centre', label: 'Centre' },
  { value: 'row', label: 'Row' },
]

export const findTemplate = (id: string) => TEMPLATES.find((t) => t.id === id)

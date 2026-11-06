import { Hash, Ruler, Sofa } from 'lucide-react'
import type { ReactNode } from 'react'
import type { PlannerState } from './plannerState'

type PreviewKey = keyof PlannerState['preview']

/** The three preview settings, shared by the toolbar toggles, menus and the mobile View tab. */
export const PREVIEW_OPTIONS: ReadonlyArray<{
  key: PreviewKey
  icon: ReactNode
  /** Short label for icon tooltips and menus. */
  short: string
  label: (frames: number) => string
  description: string
}> = [
  {
    key: 'sofa',
    icon: <Sofa />,
    short: 'Reference sofa',
    label: () => '84″ reference scale sofa',
    description: 'Shows a real-size sofa and keeps frames clear of it.',
  },
  {
    key: 'indexBadges',
    icon: <Hash />,
    short: 'Frame numbers',
    label: (n) => `Frame index badges (1–${n})`,
    description: 'Numbers each frame on the wall.',
  },
  {
    key: 'guides',
    icon: <Ruler />,
    short: 'Dimension guides',
    label: () => 'Architectural dimension guides',
    description: 'Wall size and gallery eye level. Also included in downloads.',
  },
]

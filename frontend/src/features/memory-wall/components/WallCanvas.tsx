import type { CSSProperties, Ref } from 'react'
import { cn } from '@/lib/cn'
import { formatLength, type LengthUnit } from '@/lib/units'
import { LAYOUT_STYLES, PLANNER_RULES } from '../constants'
import type { Scene } from '../lib/geometry/scene'
import { WallSvg } from './WallSvg'

interface WallCanvasProps {
  scene: Scene
  unit: LengthUnit
  showGuides: boolean
  showBadges: boolean
  interactive?: boolean
  selectedIndex?: number
  onSelect?: (index: number) => void
  svgRef?: Ref<SVGSVGElement>
  /** Max height of the canvas, any CSS length (it keeps the wall's aspect ratio). */
  maxHeight?: string
  className?: string
}

const pct = (v: number, of: number) => `${(v / of) * 100}%`

/**
 * The live wall: SVG drawing + crisp HTML overlays (dimension guides, eye-level line, frame
 * numbers) positioned in % of the wall, so they stay readable at any canvas size.
 */
export function WallCanvas({
  scene,
  unit,
  showGuides,
  showBadges,
  interactive = false,
  selectedIndex = -1,
  onSelect,
  svgRef,
  maxHeight = '62vh',
  className,
}: WallCanvasProps) {
  const { w: W, h: H } = scene.wall
  const eyeUnit: LengthUnit = unit === 'ft' ? 'in' : unit
  const style = LAYOUT_STYLES.find((s) => s.id === scene.style)?.label ?? scene.style
  const description = `${scene.frames.length} frames in a ${style.toLowerCase()} layout on a ${formatLength(W, unit)} by ${formatLength(H, unit)} wall`

  return (
    <div
      className={cn(
        '@container relative mx-auto w-full overflow-hidden rounded-xl bg-cream-200 shadow-inner',
        className,
      )}
      style={{ aspectRatio: `${W} / ${H}`, maxWidth: `calc(${maxHeight} * ${W / H})` } as CSSProperties}
    >
      <WallSvg
        scene={scene}
        interactive={interactive}
        selectedIndex={selectedIndex}
        onSelect={onSelect}
        animate
        svgRef={svgRef}
        title={description}
        className="absolute inset-0 size-full"
      />

      {showGuides && (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 text-[clamp(0.625rem,1.6cqi,0.8125rem)] font-medium text-ink-900"
        >
          {/* Width */}
          <div className="absolute top-[6%] right-[9%] left-[9%] h-px bg-ink-900/55">
            <span className="absolute top-1/2 -left-px size-2 -translate-y-1/2 rotate-45 border-b border-l border-ink-900/70" />
            <span className="absolute top-1/2 -right-px size-2 -translate-y-1/2 rotate-45 border-t border-r border-ink-900/70" />
            <span className="absolute top-1/2 left-1/2 -translate-1/2 rounded-full bg-cream-50/95 px-2.5 py-0.5 whitespace-nowrap shadow-sm">
              {formatLength(W, unit)} (Wall Width)
            </span>
          </div>
          {/* Height */}
          <div className="absolute top-[13%] bottom-[13%] left-[4.5%] w-px bg-ink-900/55">
            <span className="absolute -top-px left-1/2 size-2 -translate-x-1/2 rotate-45 border-t border-l border-ink-900/70" />
            <span className="absolute -bottom-px left-1/2 size-2 -translate-x-1/2 rotate-45 border-r border-b border-ink-900/70" />
            <span className="absolute top-1/2 left-2 -translate-y-1/2 rounded-lg bg-cream-50/90 px-2 py-0.5 text-center leading-tight shadow-sm">
              {formatLength(H, unit)}
              <br />
              <span className="text-ink-500">(Wall Height)</span>
            </span>
          </div>
          {/* Eye level */}
          <div
            className="absolute right-[2%] left-[2%] border-t border-dashed border-brand-700/45"
            style={{ top: pct(scene.eyeLevelY, H) }}
          >
            <span className="absolute right-0 -translate-y-1/2 rounded-full bg-cream-50/95 px-2.5 py-0.5 whitespace-nowrap shadow-sm">
              Gallery eye level ({formatLength(PLANNER_RULES.eyeLevelIn, eyeUnit)})
            </span>
          </div>
        </div>
      )}

      {showBadges && (
        <div aria-hidden className="pointer-events-none absolute inset-0">
          {scene.frames.map((f, i) => (
            <span
              key={f.id}
              className={cn(
                'absolute grid size-[clamp(1rem,2.6cqi,1.5rem)] -translate-1/3 place-items-center rounded-full text-[clamp(0.5625rem,1.4cqi,0.75rem)] font-bold shadow-md transition-[left,top] duration-500',
                i === selectedIndex
                  ? 'bg-brand-700 text-white ring-2 ring-white'
                  : 'bg-cream-50 text-brand-700 ring-1 ring-brand-600/40',
              )}
              style={{ left: pct(f.outer.x, W), top: pct(f.outer.y, H) }}
            >
              {f.number}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

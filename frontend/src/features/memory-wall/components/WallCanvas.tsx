import type { CSSProperties, Ref } from 'react'
import { cn } from '@/lib/cn'
import { formatLength, type LengthUnit } from '@/lib/units'
import { LAYOUT_STYLES, PLANNER_RULES } from '../constants'
import type { Scene } from '../lib/geometry/scene'
import { drawingHeight } from '../lib/room'
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
  /**
   * `container`: fill the nearest size container (`container-type: size`) on BOTH axes while
   * keeping the drawing's proportions (the studio stage). Otherwise the height is capped by
   * `maxHeight` and the width follows (dialogs).
   */
  fit?: 'container' | 'max-height'
  /** Max height of the canvas in `max-height` mode, any CSS length. */
  maxHeight?: string
  /** Light sweep over the wall while a layout is being generated. */
  busy?: boolean
  className?: string
}

const pct = (v: number, of: number) => `${(v / of) * 100}%`

const pill =
  'rounded-full bg-ivory-50/90 px-2 py-0.5 whitespace-nowrap text-charcoal-800 shadow-[0_1px_3px_rgb(31_27_25/0.18)] ring-1 ring-black/5 backdrop-blur-sm'

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
  fit = 'max-height',
  maxHeight = '62vh',
  busy = false,
  className,
}: WallCanvasProps) {
  const { w: W, h: H } = scene.wall
  const VH = drawingHeight(H)
  const ratio = W / VH
  const eyeUnit: LengthUnit = unit === 'ft' ? 'in' : unit
  const style = LAYOUT_STYLES.find((s) => s.id === scene.style)?.label ?? scene.style
  const description = `${scene.frames.length} frames in a ${style.toLowerCase()} layout on a ${formatLength(W, unit)} by ${formatLength(H, unit)} wall`

  const sizing: CSSProperties =
    fit === 'container'
      ? { aspectRatio: `${W} / ${VH}`, width: `min(100cqw, calc(100cqh * ${ratio}))` }
      : { aspectRatio: `${W} / ${VH}`, maxWidth: `calc(${maxHeight} * ${ratio})` }

  return (
    <div
      className={cn(
        '@container relative mx-auto overflow-hidden rounded-[0.625rem] bg-ivory-200',
        fit === 'max-height' && 'w-full',
        className,
      )}
      style={sizing}
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

      {/* Overlays cover the WALL only (not the floor band below it). */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0"
        style={{ height: pct(H, VH) }}
      >
        {showGuides && (
          <div className="absolute inset-0 text-[clamp(0.625rem,1.25cqi,0.75rem)] font-medium">
            {/* Width */}
            <div className="absolute top-[5%] right-[10%] left-[10%] h-px bg-charcoal-900/35">
              <span className="absolute top-1/2 left-0 h-2.5 w-px -translate-y-1/2 bg-charcoal-900/50" />
              <span className="absolute top-1/2 right-0 h-2.5 w-px -translate-y-1/2 bg-charcoal-900/50" />
              <span className={cn('absolute top-1/2 left-1/2 -translate-1/2', pill)}>
                {formatLength(W, unit)} <span className="text-charcoal-500">wide</span>
              </span>
            </div>
            {/* Height */}
            <div className="absolute top-[12%] bottom-[6%] left-[3.5%] w-px bg-charcoal-900/35">
              <span className="absolute top-0 left-1/2 h-px w-2.5 -translate-x-1/2 bg-charcoal-900/50" />
              <span className="absolute bottom-0 left-1/2 h-px w-2.5 -translate-x-1/2 bg-charcoal-900/50" />
              <span className={cn('absolute top-1/2 left-1.5 -translate-y-1/2', pill)}>
                {formatLength(H, unit)} <span className="text-charcoal-500">high</span>
              </span>
            </div>
            {/* Eye level */}
            <div
              className="absolute right-[1.5%] left-[7%] border-t border-dashed border-brand-700/40"
              style={{ top: pct(scene.eyeLevelY, H) }}
            >
              <span className={cn('absolute right-0 -translate-y-1/2', pill)}>
                Eye level · {formatLength(PLANNER_RULES.eyeLevelIn, eyeUnit)}
              </span>
            </div>
          </div>
        )}

        {showBadges &&
          scene.frames.map((f, i) => (
            <span
              key={f.id}
              className={cn(
                'absolute grid size-[clamp(1rem,2.4cqi,1.375rem)] -translate-1/3 place-items-center rounded-full text-[clamp(0.5625rem,1.3cqi,0.6875rem)] font-bold tabular-nums shadow-md transition-[left,top,background-color,transform] duration-500',
                i === selectedIndex
                  ? 'scale-110 bg-brand-600 text-white ring-2 ring-white'
                  : 'bg-ivory-50 text-charcoal-800 ring-1 ring-black/10',
              )}
              style={{ left: pct(f.outer.x, W), top: pct(f.outer.y, H) }}
            >
              {f.number}
            </span>
          ))}
      </div>

      {busy && (
        <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
          <div className="absolute inset-y-0 -left-1/2 w-[200%] animate-[shimmer_1.1s_ease-in-out_infinite] bg-[linear-gradient(100deg,transparent_35%,rgb(255_248_236/0.45)_50%,transparent_65%)]" />
        </div>
      )}
    </div>
  )
}

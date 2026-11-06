import { memo, useId, useMemo, type KeyboardEvent, type Ref } from 'react'
import { memoryWallAssets } from '@/assets/memoryWall'
import type { Scene, SceneFrame } from '../lib/geometry/scene'
import { drawingHeight, FLOOR_BAND_IN, FLOOR_TILE, roomLayout, SKIRTING_IN, type RoomItem } from '../lib/room'

interface WallSvgProps {
  scene: Scene
  /** Frames become focusable buttons that report clicks. */
  interactive?: boolean
  selectedIndex?: number
  onSelect?: (index: number) => void
  /** Animate frames to new positions when the layout recalculates. */
  animate?: boolean
  /** Lighter rendering for thumbnails (no shadows/sheen/decor). */
  detail?: 'full' | 'low'
  svgRef?: Ref<SVGSVGElement>
  className?: string
  /** Accessible description of the whole wall. */
  title?: string
}

const strip = memoryWallAssets.room.floorStrip

/**
 * Pure SVG rendering of a Scene. The viewBox is the wall in inches plus a strip of floor below
 * it, so every rect from the geometry engine is drawn 1:1 and the browser handles scaling. Only
 * presentation attributes (no CSS classes) carry visuals, so a clone can be exported as a PNG.
 *
 * Layers: painted wall + soft window light → skirting/floor strip → lamp glow → frames → room
 * cut-outs (sofa, lamp, plant), which stand in front of the wall and ignore the pointer.
 */
function WallSvgImpl({
  scene,
  interactive = false,
  selectedIndex = -1,
  onSelect,
  animate = false,
  detail = 'full',
  svgRef,
  className,
  title,
}: WallSvgProps) {
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, '')
  const id = (name: string) => `${uid}-${name}`
  const { w: W, h: H, paintHex } = scene.wall
  const VH = drawingHeight(H)
  const full = detail === 'full'
  const room = useMemo(() => roomLayout(scene), [scene])
  const decor = full ? room.decor : []
  const lamp = decor.find((d) => d.kind === 'lamp')

  const onKey = (index: number) => (e: KeyboardEvent<SVGGElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onSelect?.(index)
    }
  }

  const tile = FLOOR_TILE
  const floorTop = H - SKIRTING_IN

  return (
    <svg
      ref={svgRef}
      viewBox={`0 0 ${W} ${VH}`}
      preserveAspectRatio="xMidYMid meet"
      className={className}
      role={interactive ? 'group' : 'img'}
      aria-label={title}
    >
      <defs>
        <radialGradient id={id('light')} cx="0.16" cy="0.02" r="0.95">
          <stop offset="0" stopColor="#fff8ec" stopOpacity="0.42" />
          <stop offset="0.55" stopColor="#fff8ec" stopOpacity="0.06" />
          <stop offset="1" stopColor="#000" stopOpacity="0.08" />
        </radialGradient>
        <linearGradient id={id('ceiling')} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#2a1712" stopOpacity="0.1" />
          <stop offset="1" stopColor="#2a1712" stopOpacity="0" />
        </linearGradient>
        <linearGradient id={id('floorShade')} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#2a1712" stopOpacity="0.05" />
          <stop offset="1" stopColor="#1b0f0a" stopOpacity="0.38" />
        </linearGradient>
        {/* Floor strip tiled as [tile | mirrored tile], centred on the wall: seamless at any width. */}
        <pattern
          id={id('floor')}
          patternUnits="userSpaceOnUse"
          x={W / 2 - tile.widthIn}
          y={floorTop}
          width={tile.widthIn * 2}
          height={tile.heightIn}
        >
          <FloorTile />
          <g transform={`translate(${tile.widthIn * 2} 0) scale(-1 1)`}>
            <FloorTile />
          </g>
        </pattern>
        <radialGradient id={id('contact')}>
          <stop offset="0" stopColor="#1b0f0a" stopOpacity="0.45" />
          <stop offset="1" stopColor="#1b0f0a" stopOpacity="0" />
        </radialGradient>
        <radialGradient id={id('glow')}>
          <stop offset="0" stopColor="#ffd9a0" stopOpacity="0.55" />
          <stop offset="0.6" stopColor="#ffd9a0" stopOpacity="0.12" />
          <stop offset="1" stopColor="#ffd9a0" stopOpacity="0" />
        </radialGradient>
        <linearGradient id={id('sheen')} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#fff" stopOpacity="0.28" />
          <stop offset="0.45" stopColor="#fff" stopOpacity="0" />
          <stop offset="1" stopColor="#000" stopOpacity="0.28" />
        </linearGradient>
        <filter id={id('shadow')} x="-20%" y="-20%" width="140%" height="150%">
          <feDropShadow dx="0.35" dy="0.9" stdDeviation="0.9" floodColor="#3b2414" floodOpacity="0.38" />
        </filter>
      </defs>

      {/* Wall */}
      <rect width={W} height={H} fill={paintHex} />
      <rect width={W} height={H} fill={`url(#${id('light')})`} />
      <rect width={W} height={Math.min(H * 0.16, 24)} fill={`url(#${id('ceiling')})`} />

      {/* Skirting + floor */}
      <rect x={0} y={floorTop} width={W} height={VH - floorTop} fill={`url(#${id('floor')})`} />
      <rect x={0} y={H} width={W} height={FLOOR_BAND_IN} fill={`url(#${id('floorShade')})`} />

      {/* Warm pool of light from the lamp shade, on the wall behind the frames */}
      {lamp && (
        <ellipse
          cx={lamp.rect.x + lamp.rect.w / 2}
          cy={lamp.rect.y + 6}
          rx={34}
          ry={30}
          fill={`url(#${id('glow')})`}
        />
      )}

      {/* Frames */}
      {scene.frames.map((f, i) => (
        <FrameShape
          key={f.id}
          frame={f}
          ids={{ sheen: id('sheen'), shadow: id('shadow') }}
          full={full}
          animate={animate}
          selected={i === selectedIndex}
          interactive={interactive}
          onClick={() => onSelect?.(i)}
          onKeyDown={onKey(i)}
        />
      ))}

      {/* Room cut-outs stand in front of the wall */}
      {room.sofa && (
        <g pointerEvents="none">
          {[room.sofa, ...decor].map((it) => (
            <ellipse
              key={`${it.kind}-shadow`}
              cx={it.rect.x + it.rect.w / 2}
              cy={it.rect.y + it.rect.h - 0.4}
              rx={it.rect.w * 0.56}
              ry={it.kind === 'sofa' ? 2.4 : 1.6}
              fill={`url(#${id('contact')})`}
            />
          ))}
          {[room.sofa, ...decor].map((it) => (
            <RoomCutout key={it.kind} item={it} />
          ))}
        </g>
      )}
    </svg>
  )
}

function FloorTile() {
  return (
    <svg
      width={FLOOR_TILE.widthIn}
      height={FLOOR_TILE.heightIn}
      viewBox={FLOOR_TILE.viewBox}
      preserveAspectRatio="none"
    >
      <image href={strip.src} width={strip.width} height={strip.height} preserveAspectRatio="none" />
    </svg>
  )
}

function RoomCutout({ item }: { item: RoomItem }) {
  const { rect, crop } = item
  return (
    <svg
      x={rect.x}
      y={rect.y}
      width={rect.w}
      height={rect.h}
      viewBox={`${crop.x} ${crop.y} ${crop.w} ${crop.h}`}
      preserveAspectRatio="none"
    >
      <image href={item.src} width={item.srcWidth} height={item.srcHeight} preserveAspectRatio="none" />
    </svg>
  )
}

interface FrameShapeProps {
  frame: SceneFrame
  ids: { sheen: string; shadow: string }
  full: boolean
  animate: boolean
  selected: boolean
  interactive: boolean
  onClick: () => void
  onKeyDown: (e: KeyboardEvent<SVGGElement>) => void
}

function FrameShape({
  frame,
  ids,
  full,
  animate,
  selected,
  interactive,
  onClick,
  onKeyDown,
}: FrameShapeProps) {
  const { outer, inner, photoRect } = frame
  const w = outer.w
  const h = outer.h
  // Local coordinates (the group is translated to the frame's position).
  const ix = inner.x - outer.x
  const iy = inner.y - outer.y
  const px = photoRect.x - outer.x
  const py = photoRect.y - outer.y
  const plus = Math.min(photoRect.w, photoRect.h) * 0.16

  return (
    <g
      data-tx={outer.x}
      data-ty={outer.y}
      transform={`translate(${outer.x} ${outer.y})`}
      style={{
        transform: `translate(${outer.x}px, ${outer.y}px)`,
        transition: animate ? 'transform 480ms cubic-bezier(0.2, 0.8, 0.2, 1)' : undefined,
      }}
      className={interactive ? 'wall-frame' : undefined}
      role={interactive ? 'button' : undefined}
      tabIndex={interactive ? 0 : undefined}
      aria-label={interactive ? frame.label : undefined}
      aria-pressed={interactive ? selected : undefined}
      onClick={interactive ? onClick : undefined}
      onKeyDown={interactive ? onKeyDown : undefined}
    >
      {/* Moulding */}
      <rect
        width={w}
        height={h}
        rx={0.12}
        fill={frame.finishHex}
        filter={full ? `url(#${ids.shadow})` : undefined}
      />
      {full && <rect width={w} height={h} rx={0.12} fill={`url(#${ids.sheen})`} />}
      {/* Mount board */}
      {frame.mountHex && <rect x={ix} y={iy} width={inner.w} height={inner.h} fill={frame.mountHex} />}
      {full && (
        <rect
          x={ix}
          y={iy}
          width={inner.w}
          height={inner.h}
          fill="none"
          stroke="#000"
          strokeOpacity="0.22"
          strokeWidth={0.14}
        />
      )}
      {/* Photo or empty slot */}
      {frame.photo ? (
        <>
          <image
            href={frame.photo.href}
            x={px}
            y={py}
            width={photoRect.w}
            height={photoRect.h}
            preserveAspectRatio="xMidYMid slice"
            opacity={frame.photo.isFill ? 0.92 : 1}
          />
          {frame.mountHex && full && (
            <rect
              x={px}
              y={py}
              width={photoRect.w}
              height={photoRect.h}
              fill="none"
              stroke="#fff"
              strokeOpacity="0.5"
              strokeWidth={0.1}
            />
          )}
        </>
      ) : (
        <g>
          <rect x={px} y={py} width={photoRect.w} height={photoRect.h} fill="#efe6da" />
          <rect
            x={px + 0.4}
            y={py + 0.4}
            width={Math.max(0, photoRect.w - 0.8)}
            height={Math.max(0, photoRect.h - 0.8)}
            fill="none"
            stroke="#9f8b77"
            strokeWidth={0.12}
            strokeDasharray="0.6 0.45"
          />
          <path
            d={`M${px + photoRect.w / 2 - plus} ${py + photoRect.h / 2}h${plus * 2}M${px + photoRect.w / 2} ${py + photoRect.h / 2 - plus}v${plus * 2}`}
            stroke="#9f8b77"
            strokeWidth={Math.max(0.15, plus * 0.18)}
            strokeLinecap="round"
          />
        </g>
      )}
      {/* Hover, selection and keyboard focus (UI only, never exported) */}
      {interactive && (
        <g data-export="exclude">
          {!selected && (
            <rect
              className="wall-frame-hover"
              x={-0.8}
              y={-0.8}
              width={w + 1.6}
              height={h + 1.6}
              rx={0.5}
              fill="none"
              stroke="#d9c29a"
              strokeWidth={2}
              vectorEffect="non-scaling-stroke"
            />
          )}
          <rect
            className="wall-frame-focus"
            x={-1.6}
            y={-1.6}
            width={w + 3.2}
            height={h + 3.2}
            rx={0.7}
            fill="none"
            stroke="#1f1b19"
            strokeWidth={2}
            vectorEffect="non-scaling-stroke"
            strokeDasharray="4 3"
          />
          {selected && (
            <>
              <rect
                x={-1}
                y={-1}
                width={w + 2}
                height={h + 2}
                rx={0.6}
                fill="none"
                stroke="#9b1118"
                strokeOpacity="0.28"
                strokeWidth={9}
                vectorEffect="non-scaling-stroke"
              />
              <rect
                x={-1}
                y={-1}
                width={w + 2}
                height={h + 2}
                rx={0.6}
                fill="none"
                stroke="#9b1118"
                strokeWidth={2.5}
                vectorEffect="non-scaling-stroke"
              />
            </>
          )}
        </g>
      )}
    </g>
  )
}

/** Memoised: thumbnails re-render only when their scene changes. */
export const WallSvg = memo(WallSvgImpl)

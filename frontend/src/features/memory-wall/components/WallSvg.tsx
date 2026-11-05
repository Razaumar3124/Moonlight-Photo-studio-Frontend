import { memo, useId, type KeyboardEvent, type Ref } from 'react'
import { memoryWallAssets } from '@/assets/memoryWall'
import { ROOM_PHOTO, ROOM_PHOTO_IN } from '../constants'
import type { Scene, SceneFrame } from '../lib/geometry/scene'

interface WallSvgProps {
  scene: Scene
  /** Frames become focusable buttons that report clicks. */
  interactive?: boolean
  selectedIndex?: number
  onSelect?: (index: number) => void
  /** Animate frames to new positions when the layout recalculates. */
  animate?: boolean
  /** Lighter rendering for thumbnails (no shadows/sheen). */
  detail?: 'full' | 'low'
  svgRef?: Ref<SVGSVGElement>
  className?: string
  /** Accessible description of the whole wall. */
  title?: string
}

/** Crop the window/curtain off the left of the room photo (it would float mid-wall otherwise). */
const ROOM_CROP_LEFT_PX = 150
const roomPxPerIn = (ROOM_PHOTO.sofaRightPx - ROOM_PHOTO.sofaLeftPx) / ROOM_PHOTO.sofaWidthIn

/**
 * Pure SVG rendering of a Scene. The viewBox is the wall in inches, so every rect from the
 * geometry engine is drawn 1:1 and the browser handles scaling. Only presentation attributes
 * (no CSS classes) are used for visuals, so a clone of this SVG can be exported as a PNG.
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
  const full = detail === 'full'

  const photoX = W / 2 - ROOM_PHOTO_IN.sofaCentreX
  const photoY = H - ROOM_PHOTO_IN.height
  const cropIn = ROOM_CROP_LEFT_PX / roomPxPerIn

  const onKey = (index: number) => (e: KeyboardEvent<SVGGElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onSelect?.(index)
    }
  }

  return (
    <svg
      ref={svgRef}
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="xMidYMid meet"
      className={className}
      role={interactive ? 'group' : 'img'}
      aria-label={title}
    >
      <defs>
        <radialGradient id={id('light')} cx="0.16" cy="0.02" r="0.95">
          <stop offset="0" stopColor="#fff8ec" stopOpacity="0.45" />
          <stop offset="0.55" stopColor="#fff8ec" stopOpacity="0.08" />
          <stop offset="1" stopColor="#000" stopOpacity="0.06" />
        </radialGradient>
        <linearGradient id={id('fadeV')} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#000" />
          <stop offset="0.42" stopColor="#fff" />
        </linearGradient>
        <linearGradient id={id('fadeH')} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0" stopColor="#000" />
          <stop offset="0.1" stopColor="#fff" />
          <stop offset="0.9" stopColor="#fff" />
          <stop offset="1" stopColor="#000" />
        </linearGradient>
        <mask id={id('maskV')} maskUnits="userSpaceOnUse">
          <rect
            x={photoX}
            y={photoY}
            width={ROOM_PHOTO_IN.width}
            height={ROOM_PHOTO_IN.height}
            fill={`url(#${id('fadeV')})`}
          />
        </mask>
        <mask id={id('maskH')} maskUnits="userSpaceOnUse">
          <rect
            x={photoX + cropIn}
            y={photoY}
            width={ROOM_PHOTO_IN.width - cropIn}
            height={ROOM_PHOTO_IN.height}
            fill={`url(#${id('fadeH')})`}
          />
        </mask>
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

      {/* Room (84" reference sofa), tinted by the paint colour */}
      {scene.sofaTopY !== null ? (
        <g mask={`url(#${id('maskV')})`} style={{ mixBlendMode: 'multiply' }}>
          <g mask={`url(#${id('maskH')})`}>
            <svg
              x={photoX + cropIn}
              y={photoY}
              width={ROOM_PHOTO_IN.width - cropIn}
              height={ROOM_PHOTO_IN.height}
              viewBox={`${ROOM_CROP_LEFT_PX} 0 ${ROOM_PHOTO.widthPx - ROOM_CROP_LEFT_PX} ${ROOM_PHOTO.heightPx}`}
              preserveAspectRatio="none"
            >
              <image
                href={memoryWallAssets.roomBackground.src}
                width={ROOM_PHOTO.widthPx}
                height={ROOM_PHOTO.heightPx}
              />
            </svg>
          </g>
        </g>
      ) : (
        // Skirting board when there's no furniture
        <rect x={0} y={H - 4} width={W} height={4} fill="#000" fillOpacity="0.06" />
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
      {/* Selection + keyboard focus (UI only, never exported) */}
      {interactive && (
        <g data-export="exclude">
          <rect
            className="wall-frame-focus"
            x={-1.4}
            y={-1.4}
            width={w + 2.8}
            height={h + 2.8}
            rx={0.6}
            fill="none"
            stroke="#2a1712"
            strokeWidth={2}
            vectorEffect="non-scaling-stroke"
            strokeDasharray="4 3"
          />
          {selected && (
            <rect
              x={-0.9}
              y={-0.9}
              width={w + 1.8}
              height={h + 1.8}
              rx={0.5}
              fill="none"
              stroke="#9b1118"
              strokeWidth={3}
              vectorEffect="non-scaling-stroke"
            />
          )}
        </g>
      )}
    </g>
  )
}

/** Memoised: thumbnails re-render only when their scene changes. */
export const WallSvg = memo(WallSvgImpl)

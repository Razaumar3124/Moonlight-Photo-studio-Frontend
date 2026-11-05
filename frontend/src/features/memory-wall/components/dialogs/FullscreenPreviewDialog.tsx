import { Check, Download, Hash, LoaderCircle, Ruler, Sofa, TriangleAlert } from 'lucide-react'
import { useEffect, useRef, useState, type Dispatch, type ReactNode } from 'react'
import { Dialog } from '@/components/ui/Dialog'
import { cn } from '@/lib/cn'
import { formatLength } from '@/lib/units'
import { LAYOUT_STYLES } from '../../constants'
import { downloadWallPng } from '../../lib/exportImage'
import type { Scene } from '../../lib/geometry/scene'
import type { PlannerAction, PlannerState } from '../../lib/plannerState'
import { VariantCarousel } from '../CanvasPanel'
import { WallCanvas } from '../WallCanvas'

interface FullscreenPreviewDialogProps {
  open: boolean
  onClose: () => void
  state: PlannerState
  scene: Scene
  dispatch: Dispatch<PlannerAction>
}

/**
 * "Gallery stage" preview: the wall large on a warm spotlight backdrop, quick view toggles,
 * arrangement options (← → keys) and the Download control (moved here from the main bar).
 */
export function FullscreenPreviewDialog({
  open,
  onClose,
  state,
  scene,
  dispatch,
}: FullscreenPreviewDialogProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const unit = state.displayUnit
  const styleLabel = LAYOUT_STYLES.find((s) => s.id === scene.style)?.label ?? ''

  // ← / → browse arrangement options (not while typing).
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null
      if (t?.closest('input, textarea, select')) return
      if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
        dispatch({
          type: 'layout/setVariant',
          variant: state.layout.variant + (e.key === 'ArrowRight' ? 1 : -1),
        })
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, dispatch, state.layout.variant])

  const toggle = (key: keyof PlannerState['preview']) => () =>
    dispatch({ type: 'preview/toggle', key, value: !state.preview[key] })

  return (
    <Dialog
      open={open}
      onClose={onClose}
      size="full"
      title={state.title}
      description={`${formatLength(scene.wall.w, unit)} × ${formatLength(scene.wall.h, unit)} wall · ${scene.frames.length} frames · ${styleLabel} layout`}
      headerActions={
        <>
          <div
            role="group"
            aria-label="View options"
            className="hidden items-center gap-1 rounded-full border border-cream-300 bg-cream-100 p-1 sm:flex"
          >
            <ViewToggle
              label="Reference sofa"
              icon={<Sofa />}
              pressed={state.preview.sofa}
              onClick={toggle('sofa')}
            />
            <ViewToggle
              label="Frame numbers"
              icon={<Hash />}
              pressed={state.preview.indexBadges}
              onClick={toggle('indexBadges')}
            />
            <ViewToggle
              label="Dimension guides"
              icon={<Ruler />}
              pressed={state.preview.guides}
              onClick={toggle('guides')}
            />
          </div>
          <DownloadButton svgRef={svgRef} scene={scene} state={state} />
        </>
      }
      bodyClassName="flex flex-col items-center justify-center gap-4 bg-[radial-gradient(ellipse_at_50%_35%,#4a3329_0%,#2a1712_55%,#1a0e0b_100%)] px-3 py-4 sm:px-8 sm:py-6"
    >
      <div className="relative w-full">
        {/* Soft spotlight halo behind the wall */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-[10%] -top-6 bottom-0 rounded-full bg-gold-300/15 blur-3xl"
        />
        <WallCanvas
          scene={scene}
          unit={unit}
          showGuides={state.preview.guides}
          showBadges={state.preview.indexBadges}
          svgRef={svgRef}
          maxHeight="calc(100dvh - 15rem)"
          className="relative shadow-[0_30px_80px_-20px_rgb(0_0_0/0.7)] ring-1 ring-white/10"
        />
      </div>
      <div className="flex flex-col items-center gap-1">
        <VariantCarousel
          value={state.layout.variant}
          onChange={(v) => dispatch({ type: 'layout/setVariant', variant: v })}
          tone="dark"
        />
        <p className="hidden text-xs text-cream-300/80 sm:block">
          Use ← → to browse arrangements · Esc to close
        </p>
      </div>
    </Dialog>
  )
}

function ViewToggle({
  label,
  icon,
  pressed,
  onClick,
}: {
  label: string
  icon: ReactNode
  pressed: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      aria-pressed={pressed}
      onClick={onClick}
      className={cn(
        'grid size-8 place-items-center rounded-full transition-colors [&>svg]:size-4',
        pressed
          ? 'bg-brand-600 text-white shadow-button'
          : 'text-ink-500 hover:bg-cream-200 hover:text-ink-900',
      )}
    >
      {icon}
    </button>
  )
}

type DownloadStatus = 'idle' | 'busy' | 'done' | 'error'

const STATUS_MESSAGE: Record<DownloadStatus, string> = {
  idle: '',
  busy: 'Preparing your image…',
  done: 'Your wall design was downloaded as a PNG.',
  error: 'We couldn’t create the image. Please try again.',
}

/**
 * Prominent download control: crimson pill with a gold-ring glow on hover, press-down on click,
 * spinner while rendering, check mark when done. Feedback stays inside the dialog (a page toast
 * would sit underneath the modal's top layer, invisible and unreachable).
 */
function DownloadButton({
  svgRef,
  scene,
  state,
}: {
  svgRef: React.RefObject<SVGSVGElement | null>
  scene: Scene
  state: PlannerState
}) {
  const [status, setStatus] = useState<DownloadStatus>('idle')
  const timer = useRef<number | undefined>(undefined)
  useEffect(() => () => window.clearTimeout(timer.current), [])

  const onClick = async () => {
    const svg = svgRef.current
    if (!svg || status === 'busy') return
    window.clearTimeout(timer.current)
    setStatus('busy')
    try {
      await downloadWallPng(svg, scene, {
        title: state.title,
        unit: state.displayUnit,
        guides: state.preview.guides,
      })
      setStatus('done')
      timer.current = window.setTimeout(() => setStatus('idle'), 2200)
    } catch {
      // Stays in the error state ("Try again") until the next attempt.
      setStatus('error')
    }
  }

  const icon = {
    idle: <Download aria-hidden className="transition-transform group-hover:translate-y-0.5" />,
    busy: <LoaderCircle aria-hidden className="animate-spin" />,
    done: <Check aria-hidden />,
    error: <TriangleAlert aria-hidden />,
  }[status]

  return (
    <>
      <span role="status" className="sr-only">
        {STATUS_MESSAGE[status]}
      </span>
      <button
        type="button"
        onClick={onClick}
        aria-busy={status === 'busy' || undefined}
        title={status === 'error' ? STATUS_MESSAGE.error : 'Download as PNG'}
        className={cn(
          'group relative inline-flex h-10 items-center gap-2 rounded-full pr-4 pl-3 text-sm font-semibold text-white shadow-button transition-[transform,box-shadow,background-color] duration-200',
          'hover:-translate-y-0.5 hover:shadow-[0_8px_22px_-6px_rgb(155_17_24/0.6),0_0_0_3px_rgb(223_188_120/0.45)] active:translate-y-0 active:scale-95',
          status === 'done'
            ? 'bg-success-500'
            : status === 'error'
              ? 'bg-danger-600'
              : 'bg-linear-to-r from-brand-700 to-brand-500',
          '[&>svg]:size-5',
        )}
      >
        {icon}
        <span>
          {{ idle: 'Download', busy: 'Preparing…', done: 'Downloaded', error: 'Try again' }[status]}
        </span>
      </button>
    </>
  )
}

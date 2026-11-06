import { Check, Download, LoaderCircle, TriangleAlert } from 'lucide-react'
import { useRef, type Dispatch } from 'react'
import { Dialog } from '@/components/ui/Dialog'
import { cn } from '@/lib/cn'
import { formatLength } from '@/lib/units'
import { LAYOUT_STYLES } from '../../constants'
import { DOWNLOAD_MESSAGE, useWallDownload } from '../../hooks/useWallDownload'
import type { Scene } from '../../lib/geometry/scene'
import type { PlannerAction, PlannerState } from '../../lib/plannerState'
import { ViewToggles } from '../ViewToggles'
import { WallCanvas } from '../WallCanvas'

interface FullscreenPreviewDialogProps {
  open: boolean
  onClose: () => void
  state: PlannerState
  scene: Scene
  dispatch: Dispatch<PlannerAction>
}

/**
 * "Gallery stage" preview: the wall large on a warm spotlight backdrop, quick view toggles and
 * the Download control. Arrangement variations live with Generate Layout (Variations menu).
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

  return (
    <Dialog
      open={open}
      onClose={onClose}
      size="full"
      title={state.title}
      description={`${formatLength(scene.wall.w, unit)} × ${formatLength(scene.wall.h, unit)} wall · ${scene.frames.length} frames · ${styleLabel} layout`}
      headerActions={
        <>
          <ViewToggles state={state} dispatch={dispatch} tone="light" className="hidden sm:flex" />
          <DownloadButton svgRef={svgRef} scene={scene} state={state} />
        </>
      }
      bodyClassName="flex flex-col items-center justify-center gap-3 bg-[radial-gradient(ellipse_at_50%_30%,var(--color-stage-700)_0%,var(--color-stage-900)_55%,var(--color-stage-950)_100%)] px-3 py-4 sm:px-8 sm:py-6"
    >
      <div className="[container-type:size] relative flex min-h-0 w-full flex-1 items-center justify-center">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-[12%] top-0 bottom-[10%] rounded-full bg-champagne-300/10 blur-3xl"
        />
        <WallCanvas
          scene={scene}
          unit={unit}
          showGuides={state.preview.guides}
          showBadges={state.preview.indexBadges}
          svgRef={svgRef}
          fit="container"
          className="relative shadow-wall ring-1 ring-white/10"
        />
      </div>
      <p className="hidden shrink-0 text-xs text-ivory-200/60 sm:block">Esc to close</p>
    </Dialog>
  )
}

/**
 * Download control: crimson pill, spinner while rendering, check mark when done. Feedback stays
 * inside the dialog (a page toast would sit underneath the modal's top layer).
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
  const { status, download } = useWallDownload(svgRef, scene, state)

  const icon = {
    idle: <Download aria-hidden className="transition-transform group-hover:translate-y-0.5" />,
    busy: <LoaderCircle aria-hidden className="animate-spin" />,
    done: <Check aria-hidden />,
    error: <TriangleAlert aria-hidden />,
  }[status]

  return (
    <>
      <span role="status" className="sr-only">
        {DOWNLOAD_MESSAGE[status]}
      </span>
      <button
        type="button"
        onClick={() => void download()}
        aria-busy={status === 'busy' || undefined}
        title={status === 'error' ? DOWNLOAD_MESSAGE.error : 'Download as PNG'}
        className={cn(
          'group relative inline-flex h-9 items-center gap-2 rounded-lg pr-3.5 pl-3 text-[0.8125rem] font-semibold text-white shadow-primary transition-[transform,box-shadow,background-color] duration-200',
          'hover:-translate-y-px active:translate-y-0 active:scale-[0.98]',
          status === 'done'
            ? 'bg-success-500'
            : status === 'error'
              ? 'bg-danger-600'
              : 'bg-brand-600 hover:bg-brand-700',
          '[&>svg]:size-4',
        )}
      >
        {icon}
        <span>
          {{ idle: 'Download PNG', busy: 'Preparing…', done: 'Downloaded', error: 'Try again' }[status]}
        </span>
      </button>
    </>
  )
}

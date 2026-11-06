import { Download, Expand, MoreHorizontal, RotateCcw, Shuffle, Sparkles, WandSparkles } from 'lucide-react'
import { useCallback, type Dispatch, type RefObject } from 'react'
import { useToast } from '@/components/feedback/toastContext'
import { Button } from '@/components/ui/Button'
import { IconButton } from '@/components/ui/IconButton'
import { Menu, type MenuSection } from '@/components/ui/Menu'
import { SegmentedControl } from '@/components/ui/SegmentedControl'
import { cn } from '@/lib/cn'
import { formatLength } from '@/lib/units'
import { LAYOUT_STYLES, type LayoutStyleId } from '../constants'
import { DOWNLOAD_MESSAGE, useWallDownload } from '../hooks/useWallDownload'
import type { Scene } from '../lib/geometry/scene'
import type { PlannerAction, PlannerState } from '../lib/plannerState'
import { PREVIEW_OPTIONS } from '../lib/previewOptions'
import { ViewToggles } from './ViewToggles'
import { WallCanvas } from './WallCanvas'

export interface GenerateHandlers {
  generating: boolean
  onGenerate: () => void
  onRegenerate: () => void
  onRedesign: () => void
}

interface StageProps extends GenerateHandlers {
  state: PlannerState
  dispatch: Dispatch<PlannerAction>
  scene: Scene
  svgRef: RefObject<SVGSVGElement | null>
  onSelectFrame: (index: number) => void
  onReset: () => void
  onFullscreen: () => void
  /** Show Regenerate / Redesign / Generate in the footer (phones keep them in the bottom bar). */
  showGenerate?: boolean
  className?: string
}

/**
 * Centre of the studio: the wall on a dark, softly lit stage. Toolbar = what you see (layout
 * style, view toggles, fullscreen, more); footer = live summary + generation controls.
 * Sized by its grid cell; the canvas fits the remaining space on both axes.
 */
export function Stage({
  state,
  dispatch,
  scene,
  svgRef,
  onSelectFrame,
  onReset,
  onFullscreen,
  showGenerate = true,
  className,
  ...generate
}: StageProps) {
  const toast = useToast()
  const unit = state.displayUnit
  const a = scene.arrangement
  const { status, download } = useWallDownload(svgRef, scene, state)
  // Stable callback, so the memoised WallSvg skips renders that don't change the drawing.
  const onSelect = useCallback((index: number) => onSelectFrame(index), [onSelectFrame])

  const runDownload = async () => {
    const result = await download()
    if (result === 'done') toast({ tone: 'success', message: DOWNLOAD_MESSAGE.done })
    else if (result === 'error') toast({ tone: 'error', message: DOWNLOAD_MESSAGE.error })
  }

  const moreSections = (): MenuSection[] => [
    {
      id: 'view',
      label: 'View',
      items: PREVIEW_OPTIONS.map((opt) => ({
        id: opt.key,
        kind: 'checkbox' as const,
        checked: state.preview[opt.key],
        icon: opt.icon,
        label: opt.short,
        keepOpen: true,
        onSelect: () => dispatch({ type: 'preview/toggle', key: opt.key, value: !state.preview[opt.key] }),
      })),
    },
    {
      id: 'export',
      items: [
        {
          id: 'download',
          icon: <Download />,
          label: status === 'busy' ? 'Preparing image…' : 'Download PNG',
          description: 'High-resolution image of this wall',
          disabled: status === 'busy',
          onSelect: () => void runDownload(),
        },
        {
          id: 'fullscreen',
          icon: <Expand />,
          label: 'Preview fullscreen',
          onSelect: onFullscreen,
        },
      ],
    },
    {
      id: 'planner',
      items: [
        {
          id: 'reset',
          icon: <RotateCcw />,
          label: 'Reset planner',
          description: 'Back to the default wall. You can undo this.',
          danger: true,
          onSelect: onReset,
        },
      ],
    },
  ]

  const arrangementUnit = unit === 'ft' ? 'in' : unit
  const summary = `${formatLength(a.w, arrangementUnit)} × ${formatLength(a.h, arrangementUnit)} arrangement · ${scene.frames.length} ${scene.frames.length === 1 ? 'frame' : 'frames'} · ${Math.round(scene.coverage * 100)}% of wall`

  return (
    <section
      aria-label="Wall preview"
      className={cn(
        '@container/stage relative flex min-h-0 min-w-0 flex-col bg-stage-900 text-ivory-100',
        className,
      )}
    >
      {/* Spotlight */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_70%_60%_at_50%_42%,var(--color-stage-700)_0%,transparent_75%)] opacity-80"
      />

      <div className="relative z-10 flex h-(--pl-bar) shrink-0 items-center justify-between gap-2 px-(--pl-stage-pad)">
        <SegmentedControl<LayoutStyleId>
          label="Layout style"
          appearance="stage"
          size="xs"
          options={LAYOUT_STYLES.map((s) => ({ value: s.id, label: s.label }))}
          value={state.layout.style}
          onChange={(style) => dispatch({ type: 'layout/setStyle', style })}
          className="w-[16rem] min-w-0 shrink @max-md/stage:w-auto @max-md/stage:flex-1"
        />
        <div className="flex shrink-0 items-center gap-1">
          <ViewToggles state={state} dispatch={dispatch} tone="stage" className="hidden @2xl/stage:flex" />
          <IconButton
            label="Preview fullscreen"
            icon={<Expand />}
            variant="stage"
            shape="square"
            size="sm"
            tooltip="bottom"
            onClick={onFullscreen}
          />
          <Menu
            label="More options"
            iconOnly
            tooltip="bottom"
            trigger={<MoreHorizontal aria-hidden className="size-4" />}
            triggerClassName="grid size-8 place-items-center rounded-lg text-ivory-100/80 transition-colors hover:bg-white/10 hover:text-white aria-expanded:bg-white/10 aria-expanded:text-white"
            sections={moreSections}
          />
        </div>
      </div>

      <div className="relative min-h-0 flex-1 px-(--pl-stage-pad)">
        <div className="[container-type:size] grid size-full place-items-center">
          <WallCanvas
            scene={scene}
            unit={unit}
            showGuides={state.preview.guides}
            showBadges={state.preview.indexBadges}
            interactive
            selectedIndex={state.selectedIndex}
            onSelect={onSelect}
            svgRef={svgRef}
            fit="container"
            busy={generate.generating}
            className="shadow-wall ring-1 ring-white/10"
          />
        </div>
      </div>

      <div className="relative z-10 flex h-(--pl-footer) shrink-0 items-center justify-between gap-3 px-(--pl-stage-pad)">
        {/* Live summary: announced politely so screen-reader users hear layout changes. */}
        <p
          aria-live="polite"
          className={cn(
            'min-w-0 truncate text-xs text-ivory-200/70 tabular-nums',
            showGenerate && '@max-xl/stage:sr-only',
          )}
        >
          {summary}
        </p>
        {showGenerate && <GenerateCluster tone="stage" {...generate} />}
      </div>
    </section>
  )
}

/**
 * Regenerate · Redesign · Generate Layout. Generate is the one crimson action in the workspace and
 * runs the existing best-fit generation directly.
 */
export function GenerateCluster({
  generating,
  onGenerate,
  onRegenerate,
  onRedesign,
  tone,
  className,
}: GenerateHandlers & {
  /** `stage`: footer of the dark stage. `bar`: the phone bottom bar (icon-only secondaries). */
  tone: 'stage' | 'bar'
  className?: string
}) {
  const bar = tone === 'bar'
  const secondary = cn(
    bar
      ? 'grid size-11 shrink-0 place-items-center rounded-lg text-charcoal-700 hover:bg-ivory-200 active:bg-ivory-300 [&>svg]:size-5'
      : '',
  )

  return (
    <div className={cn('flex shrink-0 items-center gap-1.5', className)}>
      {bar ? (
        <>
          <IconButton
            label="Regenerate: same style, new order"
            icon={<Shuffle />}
            variant="quiet"
            shape="square"
            tooltip="top"
            className={secondary}
            onClick={onRegenerate}
          />
          <IconButton
            label="Redesign: try a different composition"
            icon={<WandSparkles />}
            variant="quiet"
            shape="square"
            tooltip="top"
            className={secondary}
            onClick={onRedesign}
          />
        </>
      ) : (
        <>
          <StageAction
            label="Regenerate"
            hint="Same style, new order"
            icon={<Shuffle aria-hidden />}
            onClick={onRegenerate}
          />
          <StageAction
            label="Redesign"
            hint="Try a different composition"
            icon={<WandSparkles aria-hidden />}
            onClick={onRedesign}
          />
        </>
      )}

      <Button
        size="compact"
        className={cn(
          'font-semibold shadow-primary',
          bar ? 'h-11 min-w-0 flex-1 text-sm' : 'text-[0.8125rem]',
        )}
        leftIcon={<Sparkles aria-hidden className="size-4" />}
        loading={generating}
        loadingText={bar ? 'Finding…' : 'Finding the best layout…'}
        onClick={onGenerate}
      >
        {bar ? (
          'Generate'
        ) : (
          <>
            Generate<span className="@max-lg/stage:hidden"> Layout</span>
          </>
        )}
      </Button>
    </div>
  )
}

function StageAction({
  label,
  hint,
  icon,
  onClick,
}: {
  label: string
  hint: string
  icon: React.ReactNode
  onClick: () => void
}) {
  return (
    <Button
      variant="stage"
      size="compact"
      title={hint}
      aria-label={`${label}: ${hint}`}
      leftIcon={icon}
      onClick={onClick}
      className="group px-3 @max-xl/stage:px-2.5 [&>svg]:transition-transform hover:[&>svg]:rotate-12"
    >
      <span className="@max-xl/stage:sr-only">{label}</span>
    </Button>
  )
}

import {
  Bookmark,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  CircleCheck,
  LayoutGrid,
  RefreshCw,
  RotateCcw,
  WandSparkles,
} from 'lucide-react'
import { useCallback, type Dispatch, type ReactNode, type Ref } from 'react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { IconButton } from '@/components/ui/IconButton'
import { cn } from '@/lib/cn'
import { formatLength } from '@/lib/units'
import { VARIANT_COUNT } from '../constants'
import type { Scene } from '../lib/geometry/scene'
import type { PlannerAction, PlannerState } from '../lib/plannerState'
import { WallCanvas } from './WallCanvas'

interface CanvasPanelProps {
  state: PlannerState
  dispatch: Dispatch<PlannerAction>
  scene: Scene
  svgRef: Ref<SVGSVGElement>
  generating: boolean
  onSave: () => void
  onReset: () => void
  onGenerate: () => void
  onRegenerate: () => void
  onRedesign: () => void
}

/** Centre column: the live wall plus everything that changes the arrangement. */
export function CanvasPanel({
  state,
  dispatch,
  scene,
  svgRef,
  generating,
  onSave,
  onReset,
  onGenerate,
  onRegenerate,
  onRedesign,
}: CanvasPanelProps) {
  const unit = state.displayUnit
  const variant = state.layout.variant
  const a = scene.arrangement
  // Stable callback, so the memoised WallSvg skips renders that don't change the drawing.
  const onSelect = useCallback((index: number) => dispatch({ type: 'frames/select', index }), [dispatch])

  return (
    <section
      aria-labelledby="canvas-title"
      className="flex min-w-0 flex-col gap-3.5 rounded-card border border-cream-300 bg-cream-50 p-3 shadow-card sm:p-4"
    >
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <LayoutGrid aria-hidden className="size-7 shrink-0 text-brand-600" />
          <h2
            id="canvas-title"
            className="truncate font-display text-xl font-semibold text-brand-700 sm:text-2xl"
          >
            Generated Layout
          </h2>
          {scene.fits ? (
            <Badge tone="success">
              <CircleCheck aria-hidden /> Fits wall
            </Badge>
          ) : (
            <Badge tone="warning">
              <CircleAlert aria-hidden /> Check fit
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="md"
            leftIcon={<Bookmark aria-hidden className="size-4" />}
            onClick={onSave}
          >
            Save <span className="hidden sm:inline">Design</span>
          </Button>
          <Button
            variant="secondary"
            size="md"
            leftIcon={<RotateCcw aria-hidden className="size-4" />}
            onClick={onReset}
          >
            Reset
          </Button>
        </div>
      </header>

      <WallCanvas
        scene={scene}
        unit={unit}
        showGuides={state.preview.guides}
        showBadges={state.preview.indexBadges}
        interactive
        selectedIndex={state.selectedIndex}
        onSelect={onSelect}
        svgRef={svgRef}
        maxHeight="min(56vh, 36rem)"
      />

      {/* Live summary: announced politely so screen-reader users hear layout changes. */}
      <p aria-live="polite" className="text-center text-xs text-ink-500 sm:text-sm">
        Arrangement {formatLength(a.w, unit === 'ft' ? 'in' : unit)} ×{' '}
        {formatLength(a.h, unit === 'ft' ? 'in' : unit)} · {scene.frames.length}{' '}
        {scene.frames.length === 1 ? 'frame' : 'frames'} · covers {Math.round(scene.coverage * 100)}% of the
        wall
      </p>
      {scene.warnings.length > 0 && (
        <ul className="flex flex-col gap-1.5">
          {scene.warnings.map((w) => (
            <li
              key={w.code}
              className="flex items-start gap-2 rounded-lg border border-gold-300 bg-gold-100/60 px-3 py-2 text-sm text-ink-700"
            >
              <CircleAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-gold-600" />
              {w.message}
            </li>
          ))}
        </ul>
      )}

      <VariantCarousel
        value={variant}
        onChange={(v) => dispatch({ type: 'layout/setVariant', variant: v })}
      />

      <div className="grid grid-cols-2 gap-3">
        <ActionTile
          icon={<RefreshCw />}
          title="Regenerate"
          subtitle="Same style, new arrangement"
          onClick={onRegenerate}
        />
        <ActionTile
          icon={<WandSparkles />}
          title="Redesign"
          subtitle="Try a different composition"
          onClick={onRedesign}
        />
      </div>

      <Button
        size="lg"
        fullWidth
        className="h-13 font-display text-lg font-semibold"
        leftIcon={<LayoutGrid aria-hidden className="size-5" />}
        loading={generating}
        loadingText="Finding the best layout…"
        onClick={onGenerate}
      >
        Generate Layout
      </Button>
    </section>
  )
}

/** ‹ ● ○ ○ › Arrangement options. */
export function VariantCarousel({
  value,
  onChange,
  tone = 'light',
}: {
  value: number
  onChange: (v: number) => void
  tone?: 'light' | 'dark'
}) {
  return (
    <div role="group" aria-label="Layout options" className="flex items-center justify-center gap-2">
      <IconButton
        label="Previous layout option"
        icon={<ChevronLeft />}
        variant={tone === 'dark' ? 'glass' : 'outline'}
        size="sm"
        onClick={() => onChange(value - 1)}
      />
      <div className="flex items-center">
        {Array.from({ length: VARIANT_COUNT }, (_, i) => (
          <button
            key={i}
            type="button"
            aria-label={`Layout option ${i + 1} of ${VARIANT_COUNT}`}
            aria-current={i === value ? 'true' : undefined}
            onClick={() => onChange(i)}
            className="grid size-6 place-items-center rounded-full"
          >
            <span
              className={cn(
                'block rounded-full transition-all',
                i === value
                  ? 'h-2.5 w-5 bg-brand-600'
                  : cn(
                      'size-2.5',
                      tone === 'dark' ? 'bg-white/40 hover:bg-white/70' : 'bg-cream-400 hover:bg-ink-300',
                    ),
              )}
            />
          </button>
        ))}
      </div>
      <IconButton
        label="Next layout option"
        icon={<ChevronRight />}
        variant={tone === 'dark' ? 'glass' : 'outline'}
        size="sm"
        onClick={() => onChange(value + 1)}
      />
    </div>
  )
}

function ActionTile({
  icon,
  title,
  subtitle,
  onClick,
}: {
  icon: ReactNode
  title: string
  subtitle: string
  onClick: () => void
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex flex-col items-center gap-1 rounded-xl border border-cream-300 bg-white px-3 py-3 text-center shadow-field transition-[border-color,box-shadow,transform] hover:-translate-y-0.5 hover:border-brand-200 hover:shadow-card active:translate-y-0"
    >
      <span className="flex items-center gap-2 font-display text-base font-semibold text-ink-900 sm:text-lg">
        <span
          aria-hidden
          className="text-brand-600 transition-transform group-hover:rotate-12 [&>svg]:size-5"
        >
          {icon}
        </span>
        {title}
      </span>
      <span className="text-xs text-ink-500">{subtitle}</span>
    </button>
  )
}

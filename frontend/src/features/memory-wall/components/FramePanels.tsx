import {
  ChevronRight,
  Hash,
  ImagePlus,
  RectangleHorizontal,
  RectangleVertical,
  Ruler,
  Sofa,
} from 'lucide-react'
import { useId, useRef, useState, type Dispatch } from 'react'
import { samplePhotos } from '@/assets/memoryWall'
import { Alert } from '@/components/feedback/Alert'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { NumberStepper } from '@/components/ui/NumberStepper'
import { SegmentedControl } from '@/components/ui/SegmentedControl'
import { Select } from '@/components/ui/Select'
import { Switch } from '@/components/ui/Switch'
import { SwatchPicker } from '@/components/ui/SwatchPicker'
import { cn } from '@/lib/cn'
import { FRAME_SIZES, MOUNT_COLOURS, PLANNER_RULES, WOOD_FINISHES, type Orientation } from '../constants'
import { dpiQuality, effectiveDpi, type UploadResult } from '../hooks/usePhotoUpload'
import { frameGeometry } from '../lib/geometry/scene'
import type { FrameConfig, PlannerAction, PlannerState } from '../lib/plannerState'
import { StepCard } from './StepCard'

interface PanelProps {
  state: PlannerState
  dispatch: Dispatch<PlannerAction>
  collapsible?: boolean
}

type UploadPhoto = (file: File) => Promise<UploadResult>

/* ③ Frame & Photo Selection */
export function FrameSelectionPanel({
  state,
  dispatch,
  collapsible,
  onUpload,
}: PanelProps & {
  /** Owned by the page, so uploaded photos outlive this (collapsible) panel. */
  onUpload: UploadPhoto
}) {
  const index = state.selectedIndex
  const frame = state.frames[index]
  if (!frame) return null
  const finish = WOOD_FINISHES.find((f) => f.id === frame.finishId)
  const update = (patch: Partial<Omit<FrameConfig, 'id' | 'photo'>>) =>
    dispatch({ type: 'frames/update', index, patch })

  return (
    <StepCard
      step={3}
      title="Frame & Photo Selection"
      badge={<Badge>Interactive</Badge>}
      collapsible={collapsible}
    >
      <div className="flex flex-col gap-3 rounded-xl border border-cream-300 bg-cream-100/60 p-3">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="font-display text-lg font-semibold text-ink-900">Selected Frame #{index + 1}</h3>
          <button
            type="button"
            onClick={() => dispatch({ type: 'frames/applyToAll', index })}
            className="inline-flex shrink-0 items-center gap-0.5 rounded-md px-1 py-1 text-xs font-medium text-ink-700 hover:text-brand-700"
          >
            Apply to all frames <ChevronRight aria-hidden className="size-3.5" />
          </button>
        </div>
        <FrameChips
          count={state.frames.length}
          selected={index}
          onSelect={(i) => dispatch({ type: 'frames/select', index: i })}
        />
        {/* Keyed by frame: errors/progress belong to the frame they were for. */}
        <PhotoPicker key={frame.id} frame={frame} index={index} dispatch={dispatch} upload={onUpload} />
      </div>

      <Switch
        label="Fill empty frames with samples"
        checked={state.fillWithSamples}
        onChange={(value) => dispatch({ type: 'samples/toggle', value })}
      />

      <Select
        label="Frame Size"
        value={frame.sizeId}
        options={FRAME_SIZES.map((s) => ({ value: s.id, label: s.label }))}
        onChange={(e) => update({ sizeId: e.target.value })}
      />

      <SegmentedControl<Orientation>
        label="Orientation"
        options={[
          { value: 'portrait', label: 'Portrait', icon: <RectangleVertical aria-hidden /> },
          { value: 'landscape', label: 'Landscape', icon: <RectangleHorizontal aria-hidden /> },
        ]}
        value={frame.orientation}
        onChange={(orientation) => update({ orientation })}
      />

      <SwatchPicker
        label="Wood Moulding & Finish"
        options={WOOD_FINISHES}
        value={frame.finishId}
        onChange={(finishId) => update({ finishId })}
        aside={finish?.label}
        textured
      />

      <Switch
        label="Acid-Free Mount (Pass-Partout)"
        description="Museum archival bevel board"
        checked={frame.mount.enabled}
        onChange={(enabled) => dispatch({ type: 'frames/updateMount', index, patch: { enabled } })}
      />

      <SwatchPicker
        label="Mount Colour"
        options={MOUNT_COLOURS}
        value={frame.mount.colourId}
        onChange={(colourId) => dispatch({ type: 'frames/updateMount', index, patch: { colourId } })}
        disabled={!frame.mount.enabled}
      />

      <NumberStepper
        label="Mat Margin / Bevel Size"
        value={frame.mount.marginIn}
        min={PLANNER_RULES.matIn.min}
        max={PLANNER_RULES.matIn.max}
        step={PLANNER_RULES.matIn.step}
        unit="in"
        disabled={!frame.mount.enabled}
        onChange={(marginIn) => dispatch({ type: 'frames/updateMount', index, patch: { marginIn } })}
      />
    </StepCard>
  )
}

/** Frame number chips "1 2 3 …" as a radio group; scrolls sideways on narrow screens. */
function FrameChips({
  count,
  selected,
  onSelect,
}: {
  count: number
  selected: number
  onSelect: (i: number) => void
}) {
  const name = useId()
  return (
    <fieldset className="min-w-0">
      <legend className="sr-only">Choose a frame to edit</legend>
      <div className="flex flex-wrap gap-1 py-0.5">
        {Array.from({ length: count }, (_, i) => (
          <label key={i} className="shrink-0">
            <input
              type="radio"
              name={name}
              checked={i === selected}
              onChange={() => onSelect(i)}
              aria-label={`Frame ${i + 1}`}
              className="peer sr-only"
            />
            <span
              className={cn(
                'grid size-7.5 cursor-pointer place-items-center rounded-full border text-sm font-semibold transition-colors',
                'border-cream-300 bg-cream-50 text-ink-700 hover:border-cream-400',
                'peer-checked:border-brand-700 peer-checked:bg-brand-600 peer-checked:text-white peer-checked:shadow-button',
                'peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-brand-600',
              )}
            >
              {i + 1}
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}

/** Thumbnail + Upload / Replace + Remove, with print-quality feedback for uploads. */
function PhotoPicker({
  frame,
  index,
  dispatch,
  upload,
}: {
  frame: FrameConfig
  index: number
  dispatch: Dispatch<PlannerAction>
  upload: UploadPhoto
}) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const photo = frame.photo
  const sample = photo?.kind === 'sample' ? samplePhotos.find((p) => p.id === photo.sampleId) : undefined
  const thumb = photo?.kind === 'upload' ? photo.url : sample?.src

  const handleFile = async (file: File | undefined) => {
    if (!file || busy) return
    const frameId = frame.id
    setBusy(true)
    setError(null)
    const result = await upload(file)
    setBusy(false)
    if (result.ok) dispatch({ type: 'frames/setPhoto', frameId, photo: result.photo })
    else setError(result.error)
  }

  let info: React.ReactNode = 'No photo yet · JPEG, PNG or WebP up to 25 MB'
  let mismatch: Orientation | null = null
  if (photo?.kind === 'upload') {
    const g = frameGeometry(frame)
    const dpi = effectiveDpi(photo.widthPx, photo.heightPx, g.opening)
    const q = dpiQuality(dpi)
    const photoOrientation: Orientation = photo.widthPx >= photo.heightPx ? 'landscape' : 'portrait'
    if (photoOrientation !== frame.orientation) mismatch = photoOrientation
    info = (
      <>
        <span className="block truncate font-medium text-ink-700">{photo.name}</span>
        <span
          className={cn(
            q.tone === 'success'
              ? 'text-success-500'
              : q.tone === 'warning'
                ? 'text-gold-600'
                : 'text-danger-600',
          )}
        >
          {photo.widthPx} × {photo.heightPx} px · {dpi} DPI · {q.label}
        </span>
      </>
    )
  } else if (sample) {
    info = 'Archival Silver Halide 300 DPI support'
  }

  return (
    <div className="flex flex-col gap-2">
      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={(e) => {
          // dragleave also fires when moving onto a child element; only reset when really leaving.
          if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setDragOver(false)
        }}
        onDrop={(e) => {
          e.preventDefault()
          setDragOver(false)
          void handleFile(e.dataTransfer.files[0])
        }}
        className={cn(
          'flex items-center gap-3 rounded-xl border border-cream-300 bg-cream-50 p-2.5 transition-colors',
          dragOver && 'border-brand-600 bg-brand-50',
        )}
      >
        <div className="grid size-16 shrink-0 place-items-center overflow-hidden rounded-lg border-4 border-cream-200 bg-cream-200 shadow-field">
          {thumb ? (
            <img
              src={thumb}
              alt={photo?.kind === 'upload' ? photo.name : (sample?.alt ?? '')}
              className="size-full object-cover"
            />
          ) : (
            <ImagePlus aria-hidden className="size-6 text-ink-500" />
          )}
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-1.5">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <Button
              variant="secondary"
              size="md"
              className="h-9"
              leftIcon={<ImagePlus aria-hidden className="size-4" />}
              loading={busy}
              loadingText="Reading…"
              onClick={() => inputRef.current?.click()}
            >
              {photo ? 'Upload / Replace' : 'Upload photo'}
            </Button>
            <button
              type="button"
              disabled={!photo}
              onClick={() => {
                setError(null)
                dispatch({ type: 'frames/setPhoto', frameId: frame.id, photo: null })
              }}
              className="rounded-md px-1 py-1 text-sm font-semibold text-danger-600 hover:underline disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:no-underline"
            >
              Remove
            </button>
          </div>
          <p className="text-xs leading-snug text-ink-500">{info}</p>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="sr-only"
          tabIndex={-1}
          aria-label={`Upload a photo for frame ${index + 1}`}
          onChange={(e) => {
            void handleFile(e.target.files?.[0])
            e.target.value = '' // allow re-selecting the same file
          }}
        />
      </div>
      {mismatch && (
        <p className="flex flex-wrap items-center gap-2 text-xs text-ink-700">
          This photo is {mismatch}.
          <button
            type="button"
            className="font-semibold text-brand-700 underline underline-offset-2"
            onClick={() => dispatch({ type: 'frames/update', index, patch: { orientation: mismatch } })}
          >
            Switch frame to {mismatch}
          </button>
        </p>
      )}
      {error && <Alert tone="error">{error}</Alert>}
    </div>
  )
}

/* ④ Preview Settings */
export function PreviewSettingsPanel({ state, dispatch }: PanelProps) {
  const toggle = (key: keyof PlannerState['preview']) => (value: boolean) =>
    dispatch({ type: 'preview/toggle', key, value })
  return (
    <StepCard step={4} title="Preview Settings" collapsible bodyClassName="gap-4">
      <Switch
        icon={<Sofa />}
        label='84" Reference Scale Sofa'
        checked={state.preview.sofa}
        onChange={toggle('sofa')}
      />
      <Switch
        icon={<Hash />}
        label={`Frame Index badges (1-${state.frames.length})`}
        checked={state.preview.indexBadges}
        onChange={toggle('indexBadges')}
      />
      <Switch
        icon={<Ruler />}
        label="Architectural dimension guidelines"
        checked={state.preview.guides}
        onChange={toggle('guides')}
      />
    </StepCard>
  )
}

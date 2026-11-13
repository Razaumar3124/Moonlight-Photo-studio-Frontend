import {
  Check,
  ChevronLeft,
  ChevronRight,
  CopyCheck,
  Frame as FrameIcon,
  Image as ImageIcon,
  ImagePlus,
  Plus,
  RectangleHorizontal,
  RectangleVertical,
  SquareDashed,
  Upload,
} from 'lucide-react'
import { useEffect, useId, useRef, useState, type Dispatch } from 'react'
import { samplePhotos } from '@/assets/memoryWall'
import { Alert } from '@/components/feedback/Alert'
import { Button } from '@/components/ui/Button'
import { IconButton } from '@/components/ui/IconButton'
import { NumberStepper } from '@/components/ui/NumberStepper'
import { SegmentedControl } from '@/components/ui/SegmentedControl'
import { Select } from '@/components/ui/Select'
import { Switch } from '@/components/ui/Switch'
import { SwatchPicker } from '@/components/ui/SwatchPicker'
import { TabPanel, Tabs } from '@/components/ui/Tabs'
import { cn } from '@/lib/cn'
import { FRAME_SIZES, MOUNT_COLOURS, PLANNER_RULES, WOOD_FINISHES, type Orientation } from '../constants'
import { usePhotos } from '../hooks/usePhotoLibrary'
import { frameGeometry, type Scene } from '../lib/geometry/scene'
import {
  dpiQuality,
  effectiveDpi,
  PHOTO_UPLOAD_HINT,
  PHOTO_UPLOAD_HINT_LONG,
  toPhotoRef,
} from '../lib/photos'
import type { FrameConfig, PlannerAction, PlannerState } from '../lib/plannerState'
import { PREVIEW_OPTIONS } from '../lib/previewOptions'
import { MyPhotosDialog } from './dialogs/MyPhotosDialog'

interface PanelProps {
  state: PlannerState
  dispatch: Dispatch<PlannerAction>
}

type InspectorTab = 'photo' | 'frame' | 'mount'

const INSPECTOR_TABS = [
  { id: 'photo', label: 'Photo', icon: <ImageIcon aria-hidden /> },
  { id: 'frame', label: 'Frame', icon: <FrameIcon aria-hidden /> },
  { id: 'mount', label: 'Mount', icon: <SquareDashed aria-hidden /> },
] as const

/**
 * 03 · Frame inspector: which frame (header ‹ ›, thumbnail navigator, or a click on the wall)
 * and its properties grouped as Photo · Frame · Mount.
 */
export function FrameInspector({
  state,
  dispatch,
  scene,
  className,
}: PanelProps & {
  scene: Scene
  className?: string
}) {
  const [tab, setTab] = useState<InspectorTab>('photo')
  const idBase = useId()
  const index = state.selectedIndex
  const count = state.frames.length
  const frame = state.frames[index]
  if (!frame) return null

  const size = FRAME_SIZES.find((s) => s.id === frame.sizeId)
  const finish = WOOD_FINISHES.find((f) => f.id === frame.finishId)
  const select = (i: number) => dispatch({ type: 'frames/select', index: (i + count) % count })

  return (
    <div className={cn('flex min-h-full flex-col gap-[calc(var(--pl-gap)*0.66)]', className)}>
      <header className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="flex items-baseline gap-2 leading-none">
            <span
              aria-hidden
              className="font-sans text-[0.6875rem] font-semibold tracking-[0.18em] text-gold-600"
            >
              03
            </span>
            <span className="font-display text-[1.0625rem] font-semibold text-charcoal-900">
              Frame {index + 1}
            </span>
            <span className="font-sans text-xs font-medium text-charcoal-500">of {count}</span>
          </h2>
          <p className="mt-1.5 truncate text-xs text-charcoal-500">
            {size ? `${size.w} × ${size.h} in` : ''} ·{' '}
            {frame.orientation === 'portrait' ? 'Portrait' : 'Landscape'} · {finish?.label}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-0.5">
          <IconButton
            label="Previous frame"
            icon={<ChevronLeft />}
            variant="quiet"
            shape="square"
            size="xs"
            tooltip="bottom"
            disabled={count < 2}
            onClick={() => select(index - 1)}
          />
          <IconButton
            label="Next frame"
            icon={<ChevronRight />}
            variant="quiet"
            shape="square"
            size="xs"
            tooltip="bottom"
            tooltipAlign="end"
            disabled={count < 2}
            onClick={() => select(index + 1)}
          />
        </div>
      </header>

      <FrameNavigator state={state} scene={scene} onSelect={select} />

      <Tabs<InspectorTab>
        idBase={idBase}
        label="Frame properties"
        tabs={INSPECTOR_TABS}
        value={tab}
        onChange={setTab}
      />

      <TabPanel idBase={idBase} id="photo" active={tab === 'photo'} className="flex flex-col gap-3">
        {/* Keyed by frame: errors/progress belong to the frame they were for. */}
        <PhotoPicker key={frame.id} frame={frame} index={index} dispatch={dispatch} />
        <Switch
          size="sm"
          label="Fill empty frames with samples"
          description="Preview only. Your own photos are never replaced."
          checked={state.fillWithSamples}
          onChange={(value) => dispatch({ type: 'samples/toggle', value })}
        />
      </TabPanel>

      <TabPanel idBase={idBase} id="frame" active={tab === 'frame'} className="flex flex-col gap-3">
        <FrameStyleFields frame={frame} index={index} dispatch={dispatch} />
      </TabPanel>

      <TabPanel idBase={idBase} id="mount" active={tab === 'mount'} className="flex flex-col gap-3">
        <MountFields frame={frame} index={index} dispatch={dispatch} />
      </TabPanel>

      <ApplyToAll count={count} onApply={() => dispatch({ type: 'frames/applyToAll', index })} />
    </div>
  )
}

/** Thumbnails of every frame (photo + shape), as a radio group: arrows move, click selects. */
function FrameNavigator({
  state,
  scene,
  onSelect,
}: {
  state: PlannerState
  scene: Scene
  onSelect: (i: number) => void
}) {
  const name = useId()
  const listRef = useRef<HTMLDivElement>(null)
  const selected = state.selectedIndex

  // Keep the selected thumbnail in view (selection can come from the wall or ‹ ›). Scrolls the
  // strip itself: scrollIntoView would also scroll overflow-hidden ancestors (the app shell).
  useEffect(() => {
    const list = listRef.current
    const el = list?.querySelector<HTMLElement>(`[data-index="${selected}"]`)
    if (!list || !el) return
    const left = el.offsetLeft // the strip is `relative`, so it is the offsetParent
    const right = left + el.offsetWidth
    if (left < list.scrollLeft) list.scrollTo({ left: left - 4, behavior: 'smooth' })
    else if (right > list.scrollLeft + list.clientWidth)
      list.scrollTo({ left: right - list.clientWidth + 4, behavior: 'smooth' })
  }, [selected])

  return (
    <fieldset className="min-w-0">
      <legend className="sr-only">Choose a frame to edit</legend>
      <div
        ref={listRef}
        className="relative -mx-1 flex snap-x scroll-quiet gap-1.5 overflow-x-auto px-1 pt-1.5 pb-1.5"
      >
        {state.frames.map((f, i) => {
          const photo = scene.frames[i]?.photo
          const isSelected = i === selected
          const landscape = f.orientation === 'landscape'
          return (
            <label key={f.id} data-index={i} className="relative shrink-0 snap-start">
              <input
                type="radio"
                name={name}
                checked={isSelected}
                onChange={() => onSelect(i)}
                aria-label={`Frame ${i + 1}${f.photo ? '' : ', empty'}`}
                className="peer sr-only"
              />
              <span
                className={cn(
                  'grid h-11 w-10 cursor-pointer place-items-center rounded-lg transition-[background-color,box-shadow] duration-150',
                  'peer-checked:bg-brand-50 peer-checked:ring-2 peer-checked:ring-brand-600 hover:bg-ivory-200',
                  'peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-brand-600',
                )}
              >
                <span
                  className={cn(
                    'grid place-items-center overflow-hidden rounded-[3px] border-2 shadow-thumb',
                    landscape ? 'h-6 w-8' : 'h-8 w-6',
                    !photo && 'border-dashed border-charcoal-300 bg-ivory-200',
                  )}
                  style={photo ? { borderColor: scene.frames[i]?.finishHex } : undefined}
                >
                  {photo ? (
                    <img
                      src={photo.href}
                      alt=""
                      loading="lazy"
                      decoding="async"
                      className={cn('size-full object-cover', photo.isFill && 'opacity-70')}
                    />
                  ) : (
                    <Plus aria-hidden className="size-3 text-charcoal-300" />
                  )}
                </span>
              </span>
              <span
                aria-hidden
                className={cn(
                  'pointer-events-none absolute -top-1 -right-1 grid h-4 min-w-4 place-items-center rounded-full px-1 text-[0.5625rem] font-bold tabular-nums',
                  isSelected
                    ? 'bg-brand-600 text-white'
                    : 'bg-ivory-50 text-charcoal-700 ring-1 ring-ivory-300',
                )}
              >
                {i + 1}
              </span>
            </label>
          )
        })}
      </div>
    </fieldset>
  )
}

function FrameStyleFields({
  frame,
  index,
  dispatch,
}: {
  frame: FrameConfig
  index: number
  dispatch: Dispatch<PlannerAction>
}) {
  const finish = WOOD_FINISHES.find((f) => f.id === frame.finishId)
  const update = (patch: Partial<Omit<FrameConfig, 'id' | 'photo'>>) =>
    dispatch({ type: 'frames/update', index, patch })
  return (
    <>
      <Select
        compact
        label="Frame size"
        value={frame.sizeId}
        options={FRAME_SIZES.map((s) => ({ value: s.id, label: s.label }))}
        onChange={(e) => update({ sizeId: e.target.value })}
      />
      <SegmentedControl<Orientation>
        label="Orientation"
        showLabel
        labelClassName="mb-1.5 text-[0.8125rem] text-charcoal-700"
        appearance="neutral"
        size="xs"
        options={[
          { value: 'portrait', label: 'Portrait', icon: <RectangleVertical aria-hidden /> },
          { value: 'landscape', label: 'Landscape', icon: <RectangleHorizontal aria-hidden /> },
        ]}
        value={frame.orientation}
        onChange={(orientation) => update({ orientation })}
      />
      <SwatchPicker
        size="sm"
        label="Wood moulding & finish"
        options={WOOD_FINISHES}
        value={frame.finishId}
        onChange={(finishId) => update({ finishId })}
        aside={finish?.label}
        textured
      />
    </>
  )
}

function MountFields({
  frame,
  index,
  dispatch,
}: {
  frame: FrameConfig
  index: number
  dispatch: Dispatch<PlannerAction>
}) {
  const mount = MOUNT_COLOURS.find((m) => m.id === frame.mount.colourId)
  const patch = (p: Partial<FrameConfig['mount']>) =>
    dispatch({ type: 'frames/updateMount', index, patch: p })
  return (
    <>
      <Switch
        size="sm"
        label="Acid-free mount (pass-partout)"
        description="Museum archival bevel board"
        checked={frame.mount.enabled}
        onChange={(enabled) => patch({ enabled })}
      />
      <SwatchPicker
        size="sm"
        label="Mount colour"
        options={MOUNT_COLOURS}
        value={frame.mount.colourId}
        onChange={(colourId) => patch({ colourId })}
        aside={frame.mount.enabled ? mount?.label : 'No mount'}
        disabled={!frame.mount.enabled}
      />
      <NumberStepper
        size="sm"
        label="Mat margin / bevel"
        value={frame.mount.marginIn}
        min={PLANNER_RULES.matIn.min}
        max={PLANNER_RULES.matIn.max}
        step={PLANNER_RULES.matIn.step}
        unit="in"
        disabled={!frame.mount.enabled}
        onChange={(marginIn) => patch({ marginIn })}
      />
    </>
  )
}

/** "Apply this style to all frames", with a short confirmation in place of the label. */
function ApplyToAll({ count, onApply }: { count: number; onApply: () => void }) {
  const [done, setDone] = useState(false)
  const timer = useRef<number | undefined>(undefined)
  useEffect(() => () => window.clearTimeout(timer.current), [])
  return (
    <div className="mt-auto pt-1">
      <Button
        variant="quiet"
        size="compact"
        fullWidth
        disabled={count < 2}
        leftIcon={done ? <Check aria-hidden className="text-success-500" /> : <CopyCheck aria-hidden />}
        onClick={() => {
          onApply()
          setDone(true)
          window.clearTimeout(timer.current)
          timer.current = window.setTimeout(() => setDone(false), 1800)
        }}
      >
        {done ? `Applied to all ${count} frames` : 'Apply this style to all frames'}
      </Button>
      {/* Announced separately: a live region inside the button would drop out of its name. */}
      <span role="status" className="sr-only">
        {done ? `Style applied to all ${count} frames.` : ''}
      </span>
    </div>
  )
}

/** Thumbnail + Upload / Replace + Remove, with print-quality feedback. The whole block is a drop zone. */
function PhotoPicker({
  frame,
  index,
  dispatch,
}: {
  frame: FrameConfig
  index: number
  dispatch: Dispatch<PlannerAction>
}) {
  const library = usePhotos()
  const inputRef = useRef<HTMLInputElement>(null)
  const [error, setError] = useState<string | null>(null)
  /** The file behind the last failed upload, so "Try again" doesn't need a new pick. */
  const [failedFile, setFailedFile] = useState<File | null>(null)
  /** Shown after a photo was shrunk to fit the upload limit. */
  const [notice, setNotice] = useState<string | null>(null)
  const [progress, setProgress] = useState<number | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const [libraryOpen, setLibraryOpen] = useState(false)
  const busy = progress !== null
  const photo = frame.photo
  const sample = photo?.kind === 'sample' ? samplePhotos.find((p) => p.id === photo.sampleId) : undefined
  const uploaded = photo?.kind === 'upload' ? library.photos.find((p) => p.id === photo.photoId) : undefined
  // Library not loaded yet: don't call a photo "missing" before we know.
  const missing = photo?.kind === 'upload' && library.status === 'ready' && !uploaded
  const thumb = uploaded?.thumbnailUrl ?? sample?.src

  const handleFile = async (file: File | undefined) => {
    if (!file || busy) return
    const frameId = frame.id
    setProgress(0)
    setError(null)
    setNotice(null)
    setFailedFile(null)
    const result = await library.upload(file, { onProgress: setProgress })
    setProgress(null)
    if (result.ok) {
      dispatch({ type: 'frames/setPhoto', frameId, photo: result.photo })
      setNotice(result.notice ?? null)
    } else {
      setError(result.error)
      setFailedFile(file)
    }
  }

  let info: React.ReactNode = PHOTO_UPLOAD_HINT_LONG
  let mismatch: Orientation | null = null
  if (missing) {
    info = (
      <span className="text-danger-600">
        This photo is no longer in your library. Choose another, or remove it.
      </span>
    )
  } else if (photo?.kind === 'upload') {
    const g = frameGeometry(frame)
    const dpi = effectiveDpi(photo.widthPx, photo.heightPx, g.opening)
    const q = dpiQuality(dpi)
    const photoOrientation: Orientation = photo.widthPx >= photo.heightPx ? 'landscape' : 'portrait'
    if (photoOrientation !== frame.orientation) mismatch = photoOrientation
    info = (
      <>
        <span className="block truncate font-medium text-charcoal-700">{photo.name}</span>
        <span
          className={cn(
            'inline-flex items-center gap-1.5',
            q.tone === 'success'
              ? 'text-success-500'
              : q.tone === 'warning'
                ? 'text-gold-600'
                : 'text-danger-600',
          )}
        >
          <span aria-hidden className="size-1.5 rounded-full bg-current" />
          {photo.widthPx} × {photo.heightPx} px · {dpi} DPI · {q.label}
        </span>
      </>
    )
  } else if (sample) {
    info = (
      <>
        <span className="block font-medium text-charcoal-700">Sample photo</span>
        Archival silver halide, 300 DPI
      </>
    )
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
          'flex items-center gap-3 rounded-xl border border-dashed p-2 transition-colors duration-150',
          dragOver ? 'border-champagne-400 bg-champagne-200/30' : 'border-ivory-300 bg-ivory-100/60',
        )}
      >
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          aria-label={
            photo ? `Replace the photo in frame ${index + 1}` : `Upload a photo for frame ${index + 1}`
          }
          className="group relative grid size-[4.5rem] shrink-0 place-items-center overflow-hidden rounded-lg bg-ivory-200 shadow-thumb ring-1 ring-black/5 dense:size-16"
        >
          {thumb ? (
            <img
              src={thumb}
              alt={photo?.kind === 'upload' ? photo.name : (sample?.alt ?? '')}
              onError={photo?.kind === 'upload' ? library.reportBroken : undefined}
              className="size-full object-cover transition-transform duration-300 group-hover:scale-105"
            />
          ) : (
            <ImagePlus aria-hidden className="size-6 text-charcoal-500" />
          )}
          <span
            aria-hidden
            className="absolute inset-0 grid place-items-center bg-charcoal-900/45 text-white opacity-0 transition-opacity group-hover:opacity-100"
          >
            <Upload className="size-5" />
          </span>
        </button>
        <div className="flex min-w-0 flex-1 flex-col gap-1.5">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <Button
              variant="quiet"
              size="sm"
              leftIcon={<ImagePlus aria-hidden />}
              loading={busy}
              loadingText={progress ? `Uploading ${Math.round(progress * 100)}%` : 'Uploading…'}
              onClick={() => inputRef.current?.click()}
            >
              {photo ? 'Replace' : 'Upload photo'}
            </Button>
            <button
              type="button"
              onClick={() => setLibraryOpen(true)}
              className="rounded-md px-1.5 py-1 text-[0.8125rem] font-semibold text-brand-700 hover:underline"
            >
              My photos
            </button>
            <button
              type="button"
              disabled={!photo}
              onClick={() => {
                setError(null)
                dispatch({ type: 'frames/setPhoto', frameId: frame.id, photo: null })
              }}
              className="rounded-md px-1.5 py-1 text-[0.8125rem] font-semibold text-danger-600 hover:underline disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:no-underline"
            >
              Remove
            </button>
          </div>
          <p className="text-xs leading-snug text-charcoal-500">{info}</p>
          {(photo || missing) && (
            <p className="mt-0.5 text-[0.6875rem] leading-snug text-charcoal-500">{PHOTO_UPLOAD_HINT}</p>
          )}
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
      <p className="hidden text-[0.6875rem] text-charcoal-500 [@media(hover:hover)]:block">
        Tip: drop a photo here, or click any frame on the wall to edit it.
      </p>
      {notice && (
        <p role="status" className="text-xs text-charcoal-700">
          {notice}
        </p>
      )}
      {mismatch && (
        <p className="flex flex-wrap items-center gap-2 text-xs text-charcoal-700">
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
      {error && (
        <Alert tone="error">
          <span>{error}</span>
          {failedFile && (
            <button
              type="button"
              className="ml-2 font-semibold underline underline-offset-2"
              onClick={() => void handleFile(failedFile)}
            >
              Try again
            </button>
          )}
        </Alert>
      )}
      <MyPhotosDialog
        open={libraryOpen}
        onClose={() => setLibraryOpen(false)}
        currentPhotoId={photo?.kind === 'upload' ? photo.photoId : null}
        onChoose={(chosen) => {
          dispatch({ type: 'frames/setPhoto', frameId: frame.id, photo: toPhotoRef(chosen) })
          setLibraryOpen(false)
        }}
        onDeleted={(photoId) => dispatch({ type: 'photos/forget', photoId })}
      />
    </div>
  )
}

/** The preview settings as labelled switches (phone "View" tab, tablet side panel). */
export function ViewSettings({ state, dispatch }: PanelProps) {
  return (
    <div className="flex flex-col gap-4">
      {PREVIEW_OPTIONS.map((opt) => (
        <Switch
          key={opt.key}
          size="sm"
          icon={opt.icon}
          label={opt.label(state.frames.length)}
          description={opt.description}
          checked={state.preview[opt.key]}
          onChange={(value) => dispatch({ type: 'preview/toggle', key: opt.key, value })}
        />
      ))}
    </div>
  )
}

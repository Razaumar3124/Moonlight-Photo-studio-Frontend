import { useCallback, useEffect, useRef, useState } from 'react'
import { useToast } from '@/components/feedback/toastContext'
import { pageTitle } from '@/config/app'
import { useMediaQuery } from '@/hooks/useMediaQuery'
import { cn } from '@/lib/cn'
import { MobileActionBar } from '../components/ActionBar'
import { AiLayoutsSection, ArrangementSection, WallSection } from '../components/ConfigPanels'
import { MobileSheet, SidePanel, type SheetTab, type SidePanelTab } from '../components/ControlPanels'
import { FullscreenPreviewDialog } from '../components/dialogs/FullscreenPreviewDialog'
import { SaveDesignDialog } from '../components/dialogs/SaveDesignDialog'
import { SavedDesignsDialog } from '../components/dialogs/SavedDesignsDialog'
import { TemplatesDialog } from '../components/dialogs/TemplatesDialog'
import { FrameInspector } from '../components/FramePanels'
import { PlannerHeader } from '../components/PlannerHeader'
import { Rail } from '../components/RailSection'
import { Stage } from '../components/Stage'
import { LAYOUT_STYLES } from '../constants'
import { usePhotoUpload } from '../hooks/usePhotoUpload'
import { usePlanner } from '../hooks/usePlanner'
import { suggestLayouts } from '../lib/geometry/scene'
import type { PlannerState } from '../lib/plannerState'
import { savedDesignsStore } from '../lib/savedDesigns'
import type { PlannerTemplate } from '../lib/templates'

type DialogName = 'fullscreen' | 'templates' | 'saved' | 'save' | null

/**
 * Structure by viewport (docs/MEMORY_WALL_REDESIGN_AUDIT.md §3, §7):
 * - desktop (≥ 1280px): set-up rail · stage · frame inspector
 * - split (landscape below 1280px: tablets, small laptops, landscape phones): stage · tabbed panel
 * - stacked (portrait phones and tablets): stage on top · tabbed sheet · bottom action bar
 * Density (control heights, spacing) follows the viewport height in CSS (`.planner-scope`).
 */
type LayoutMode = 'desktop' | 'split' | 'stacked'

function useLayoutMode(): LayoutMode {
  const desktop = useMediaQuery('(min-width: 80rem)')
  const landscape = useMediaQuery('(min-aspect-ratio: 1/1) and (min-width: 30rem)')
  return desktop ? 'desktop' : landscape ? 'split' : 'stacked'
}

const styleLabel = (id: string) => LAYOUT_STYLES.find((s) => s.id === id)?.label ?? id

const isTypingTarget = (el: EventTarget | null) =>
  el instanceof HTMLElement && Boolean(el.closest('input, textarea, select, [contenteditable="true"]'))

/**
 * Memory Wall Planner: a fixed-height studio workspace. All state lives in usePlanner; this
 * page wires the regions, dialogs and toasts. Destructive actions (reset, opening a saved
 * design) offer Undo instead of a confirm.
 */
export default function MemoryWallPage() {
  const { state, dispatch, scene } = usePlanner()
  const toast = useToast()
  const mode = useLayoutMode()
  const [dialog, setDialog] = useState<DialogName>(null)
  const [generating, setGenerating] = useState(false)
  const [sideTab, setSideTab] = useState<SidePanelTab>('setup')
  const [sheetTab, setSheetTab] = useState<SheetTab>('wall')
  const [sheetExpanded, setSheetExpanded] = useState(false)
  const [typing, setTyping] = useState(false)
  const svgRef = useRef<SVGSVGElement>(null)
  // Page-level, so uploaded photos stay valid for the whole visit (layout switches, Undo).
  const uploadPhoto = usePhotoUpload()

  // Latest state for deferred work (the Generate timer), without re-creating handlers.
  const latestState = useRef(state)
  useEffect(() => {
    latestState.current = state
  })

  const generateTimer = useRef<number | undefined>(undefined)
  useEffect(() => () => window.clearTimeout(generateTimer.current), [])

  const close = () => setDialog(null)
  const undoTo = (previous: PlannerState) => () => dispatch({ type: 'design/load', state: previous })

  const handleGenerate = () => {
    if (generating) return
    window.clearTimeout(generateTimer.current)
    setGenerating(true)
    // A short beat so the action feels considered; the maths itself takes < 5 ms. Computed from
    // the state at that moment, so edits made during the beat are respected and undoable.
    generateTimer.current = window.setTimeout(() => {
      const previous = latestState.current
      const best = suggestLayouts(previous)[0]
      setGenerating(false)
      if (!best) return
      dispatch({ type: 'layout/apply', style: best.style, variant: best.variant })
      toast({
        tone: best.scene.fits ? 'success' : 'info',
        message: best.scene.fits
          ? `Best fit: ${styleLabel(best.style)} layout. Covers ${Math.round(best.scene.coverage * 100)}% of the wall.`
          : 'No layout fits these frames on this wall. Showing the closest match. Try smaller frames or a bigger wall.',
        action: { label: 'Undo', onClick: undoTo(previous) },
      })
    }, 450)
  }

  const handleReset = () => {
    const previous = state
    dispatch({ type: 'reset' })
    toast({
      message: 'Planner reset to the default wall.',
      action: { label: 'Undo', onClick: undoTo(previous) },
    })
  }

  const handleSave = (title: string) => {
    const saved = savedDesignsStore.save(state, title)
    dispatch({ type: 'design/rename', title })
    close()
    toast({
      tone: 'success',
      message: `“${saved.title}” saved to My Designs.`,
      action: { label: 'View', onClick: () => setDialog('saved') },
    })
  }

  const applyTemplate = (template: PlannerTemplate) => {
    const previous = state
    dispatch({ type: 'template/apply', template, templateId: template.id })
    toast({
      tone: 'success',
      message: `Applied “${template.name}”.`,
      action: { label: 'Undo', onClick: undoTo(previous) },
    })
  }

  const handleQuote = () =>
    toast({
      message: 'Quote requests open soon. Save your design now and request a quote from it later.',
      action: { label: 'Save design', onClick: () => setDialog('save') },
    })

  // Selecting a frame on the wall also brings its editor forward on tablets and phones.
  const selectFrame = useCallback(
    (index: number) => {
      dispatch({ type: 'frames/select', index })
      setSideTab('frame')
      setSheetTab('frame')
    },
    [dispatch],
  )

  // [ and ] step through frames (when not typing and no dialog is open).
  const frameCount = state.frames.length
  const selectedIndex = state.selectedIndex
  useEffect(() => {
    if (dialog) return
    const onKey = (e: KeyboardEvent) => {
      if ((e.key !== '[' && e.key !== ']') || e.ctrlKey || e.metaKey || e.altKey) return
      if (isTypingTarget(e.target)) return
      e.preventDefault()
      const step = e.key === ']' ? 1 : -1
      dispatch({ type: 'frames/select', index: (selectedIndex + step + frameCount) % frameCount })
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [dialog, dispatch, frameCount, selectedIndex])

  const generate = {
    generating,
    onGenerate: handleGenerate,
    onRegenerate: () => dispatch({ type: 'layout/regenerate' }),
    onRedesign: () => dispatch({ type: 'layout/redesign' }),
  }
  const panels = {
    state,
    dispatch,
    scene,
    onUpload: uploadPhoto,
    onApplyTemplate: applyTemplate,
    onOpenTemplates: () => setDialog('templates'),
  }
  const stage = (className?: string) => (
    <Stage
      state={state}
      dispatch={dispatch}
      scene={scene}
      svgRef={svgRef}
      onSelectFrame={selectFrame}
      onReset={handleReset}
      onFullscreen={() => setDialog('fullscreen')}
      showGenerate={mode !== 'stacked'}
      className={className}
      {...generate}
    />
  )

  return (
    <div
      className={cn(
        'planner-scope grid h-dvh grid-cols-[minmax(0,1fr)] grid-rows-[auto_minmax(0,1fr)] overflow-hidden bg-ivory-100 text-charcoal-700',
        'tiny:h-auto tiny:min-h-dvh tiny:overflow-visible',
      )}
    >
      <title>{pageTitle('Memory Wall Planner')}</title>
      <PlannerHeader
        title={state.title}
        scene={scene}
        unit={state.displayUnit}
        sofaOn={state.preview.sofa}
        onGenerate={handleGenerate}
        onHideSofa={() => dispatch({ type: 'preview/toggle', key: 'sofa', value: false })}
        onOpenTemplates={() => setDialog('templates')}
        onOpenDesigns={() => setDialog('saved')}
        onSave={() => setDialog('save')}
        onQuote={handleQuote}
        showQuote={mode !== 'stacked'}
      />

      {mode === 'desktop' && (
        <main className="grid min-h-0 grid-cols-[var(--pl-rail-l)_minmax(0,1fr)_var(--pl-rail-r)] grid-rows-[minmax(0,1fr)] tiny:min-h-[20rem]">
          <Rail label="Wall and layout set-up" side="left">
            <WallSection state={state} dispatch={dispatch} />
            <ArrangementSection state={state} dispatch={dispatch} />
            <AiLayoutsSection
              state={state}
              onApplyTemplate={applyTemplate}
              onOpenTemplates={() => setDialog('templates')}
            />
          </Rail>
          {stage()}
          <Rail label="Selected frame" side="right">
            <FrameInspector state={state} dispatch={dispatch} scene={scene} onUpload={uploadPhoto} />
          </Rail>
        </main>
      )}

      {mode === 'split' && (
        <main className="grid min-h-0 grid-cols-[minmax(0,1fr)_min(var(--pl-rail-r),46vw)] grid-rows-[minmax(0,1fr)] tiny:min-h-[20rem]">
          {stage()}
          <SidePanel {...panels} tab={sideTab} onTabChange={setSideTab} />
        </main>
      )}

      {mode === 'stacked' && (
        <main className="flex min-h-0 flex-col">
          {stage(
            cn(
              'shrink-0 transition-[height] duration-300 ease-out',
              sheetExpanded ? 'h-[32dvh]' : 'h-[min(50dvh,calc(75vw+7rem))]',
            ),
          )}
          <MobileSheet
            {...panels}
            tab={sheetTab}
            onTabChange={setSheetTab}
            expanded={sheetExpanded}
            onToggleExpanded={() => setSheetExpanded((v) => !v)}
            onTypingChange={setTyping}
            className="flex-1"
          />
          <MobileActionBar onQuote={handleQuote} hidden={typing} {...generate} />
        </main>
      )}

      <FullscreenPreviewDialog
        open={dialog === 'fullscreen'}
        onClose={close}
        state={state}
        scene={scene}
        dispatch={dispatch}
      />
      <TemplatesDialog
        open={dialog === 'templates'}
        onClose={close}
        state={state}
        onApply={(template) => {
          applyTemplate(template)
          close()
        }}
      />
      <SavedDesignsDialog
        open={dialog === 'saved'}
        onClose={close}
        unit={state.displayUnit}
        onSaveCurrent={() => setDialog('save')}
        onOpenDesign={(design) => {
          const previous = state
          dispatch({ type: 'design/load', state: design.state })
          close()
          toast({
            message: `Opened “${design.title}”.`,
            action: { label: 'Undo', onClick: undoTo(previous) },
          })
        }}
      />
      <SaveDesignDialog
        open={dialog === 'save'}
        onClose={close}
        defaultTitle={state.title}
        hasUploads={state.frames.some((f) => f.photo?.kind === 'upload')}
        onSave={handleSave}
      />
    </div>
  )
}

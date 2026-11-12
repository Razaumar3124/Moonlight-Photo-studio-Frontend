import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useToast } from '@/components/feedback/toastContext'
import { pageTitle } from '@/config/app'
import { useMediaQuery } from '@/hooks/useMediaQuery'
import { cn } from '@/lib/cn'
import { useAuth } from '@/features/auth/authContext'
import { isApiError } from '@/services/apiClient'
import { designsService } from '@/services/designsService'
import type { DesignListItem } from '@/types/api'
import { MobileActionBar } from '../components/ActionBar'
import { AiLayoutsSection, ArrangementSection, WallSection } from '../components/ConfigPanels'
import { MobileSheet, SidePanel, type SheetTab, type SidePanelTab } from '../components/ControlPanels'
import { CatalogGate } from '../components/CatalogGate'
import { FullscreenPreviewDialog } from '../components/dialogs/FullscreenPreviewDialog'
import { SaveDesignDialog } from '../components/dialogs/SaveDesignDialog'
import { SavedDesignsDialog } from '../components/dialogs/SavedDesignsDialog'
import { TemplatesDialog } from '../components/dialogs/TemplatesDialog'
import { FrameInspector } from '../components/FramePanels'
import { PlannerHeader } from '../components/PlannerHeader'
import { Rail } from '../components/RailSection'
import { Stage } from '../components/Stage'
import { LAYOUT_STYLES } from '../constants'
import { PhotoLibraryContext, usePhotoLibrary } from '../hooks/usePhotoLibrary'
import { usePlanner } from '../hooks/usePlanner'
import { designFingerprint, fromDesignDetail } from '../lib/designMapper'
import { describeSaveError, NEW_DESIGN, saveDesign, sessionFor, type DesignSession } from '../lib/designSave'
import { suggestLayouts } from '../lib/geometry/scene'
import { hasUnsavedChanges, loadDraft, saveDraft } from '../lib/plannerDraft'
import type { PlannerState } from '../lib/plannerState'
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
 *
 * Persistence (Phase 5): designs are saved to the account through the Designs API (each save is a
 * new immutable version), photos live in the user's library (Photos API), and the planner options
 * come from the backend catalog. Unsaved work is kept in this tab (lib/plannerDraft.ts) so a reload
 * or an expired session never loses it.
 */
export default function MemoryWallPage() {
  return (
    <CatalogGate>
      <PlannerWorkspace />
    </CatalogGate>
  )
}

function PlannerWorkspace() {
  const { user } = useAuth()
  const userId = user?.id ?? ''
  const library = usePhotoLibrary()
  // Unsaved work from before a reload or an expired session (this tab only, same user only).
  const [draft] = useState(() => (userId ? loadDraft(userId) : null))
  const { state, dispatch, scene } = usePlanner(draft?.state ?? null, library.urlFor)
  const [session, setSession] = useState<DesignSession>(draft?.session ?? NEW_DESIGN)
  const toast = useToast()
  const mode = useLayoutMode()
  const [dialog, setDialog] = useState<DialogName>(null)
  const [generating, setGenerating] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [openingId, setOpeningId] = useState<string | null>(null)
  const [sideTab, setSideTab] = useState<SidePanelTab>('setup')
  const [sheetTab, setSheetTab] = useState<SheetTab>('wall')
  const [sheetExpanded, setSheetExpanded] = useState(false)
  const [typing, setTyping] = useState(false)
  const svgRef = useRef<SVGSVGElement>(null)
  const savingRef = useRef(false)

  // Latest state for deferred work (the Generate timer), without re-creating handlers.
  const latestState = useRef(state)
  useEffect(() => {
    latestState.current = state
  })

  const generateTimer = useRef<number | undefined>(undefined)
  useEffect(() => () => window.clearTimeout(generateTimer.current), [])

  /* ------------------------- unsaved work: draft + warning ------------------------- */

  // A fresh planner starts "clean"; a restored draft without a saved design counts as unsaved.
  const baseline = useRef(draft ? '' : designFingerprint(state))
  const dirty = hasUnsavedChanges(state, session, baseline.current)
  const saveStatus = dirty ? 'unsaved' : session.designId ? 'saved' : null

  useEffect(() => {
    if (userId) saveDraft(userId, session, state)
  }, [userId, session, state])

  useEffect(() => {
    if (draft && hasUnsavedChanges(draft.state, draft.session, '')) {
      toast({ tone: 'info', message: 'Restored your unsaved work.' })
    }
    // Once, on arrival.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!dirty) return
    const warn = (event: BeforeUnloadEvent) => event.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])

  /* --------------------------------- fit rules --------------------------------- */

  const fitProblem = scene.fits
    ? null
    : (scene.warnings.find((w) => w.code !== 'LOW_COVERAGE')?.message ?? 'The layout doesn’t fit the wall.')
  const missingPhotos = useMemo(
    () =>
      library.status === 'ready'
        ? state.frames.filter((f) => f.photo?.kind === 'upload' && !library.has(f.photo.photoId)).length
        : 0,
    [library, state.frames],
  )

  const close = () => setDialog(null)
  const undoTo =
    (previous: PlannerState, previousSession: DesignSession = session) =>
    () => {
      dispatch({ type: 'design/load', state: previous })
      setSession(previousSession)
    }

  const handleGenerate = () => {
    if (generating) return
    window.clearTimeout(generateTimer.current)
    setGenerating(true)
    // A short beat so the action feels considered; the maths itself takes < 5 ms. Computed from
    // the state at that moment, so edits made during the beat are respected and undoable.
    generateTimer.current = window.setTimeout(() => {
      const previous = latestState.current
      const best = suggestLayouts({ ...previous, photoUrl: library.urlFor })[0]
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
    const previousSession = session
    dispatch({ type: 'reset' })
    setSession(NEW_DESIGN)
    toast({
      message: 'Planner reset to the default wall.',
      action: { label: 'Undo', onClick: undoTo(previous, previousSession) },
    })
  }

  /* ----------------------------------- saving ----------------------------------- */

  const requestSave = () => {
    if (fitProblem) {
      toast({
        tone: 'error',
        message: `This layout can’t be saved yet. ${fitProblem}`,
        action: { label: 'Fix with Generate', onClick: handleGenerate },
      })
      return
    }
    if (missingPhotos) {
      toast({
        tone: 'error',
        message: `${missingPhotos} ${missingPhotos === 1 ? 'photo is' : 'photos are'} no longer in your library. Replace or remove ${missingPhotos === 1 ? 'it' : 'them'} before saving.`,
      })
      return
    }
    setSaveError(null)
    setDialog('save')
  }

  const handleSave = async (title: string, asNew: boolean) => {
    if (savingRef.current) return
    savingRef.current = true
    setSaving(true)
    setSaveError(null)
    const named: PlannerState = { ...state, title }
    try {
      const result = await saveDesign({ state: named, scene, session, asNew })
      dispatch({ type: 'design/rename', title })
      setSession(result.session)
      close()
      toast({
        tone: result.outcome === 'unchanged' ? 'info' : 'success',
        message:
          result.outcome === 'created'
            ? `“${title}” saved to My Designs.`
            : result.outcome === 'new-version'
              ? `Saved “${title}” as version ${result.session.versionNumber}.`
              : result.outcome === 'updated'
                ? `Saved changes to “${title}”.`
                : 'No changes since the last save.',
        action: { label: 'View', onClick: () => setDialog('saved') },
      })
    } catch (error) {
      // 401 means the session could not be renewed: the route guard is about to send the user to
      // sign in, and the draft above keeps this work for when they are back.
      setSaveError(describeSaveError(error).message)
    } finally {
      savingRef.current = false
      setSaving(false)
    }
  }

  /* ------------------------------ opening / deleting ------------------------------ */

  const photosById = useMemo(() => new Map(library.photos.map((p) => [p.id, p])), [library.photos])

  const handleOpenDesign = async (item: DesignListItem) => {
    if (openingId) return
    setOpeningId(item.id)
    try {
      const detail = await designsService.detail(item.id)
      const loaded = fromDesignDetail(detail, photosById)
      if (!loaded) {
        toast({ tone: 'error', message: 'That design has no saved layout yet, so there is nothing to open.' })
        return
      }
      const previous = state
      const previousSession = session
      dispatch({ type: 'design/load', state: loaded.state })
      setSession(sessionFor(item.id, item.current_version_number, loaded.state))
      close()
      toast({
        message: `Opened “${loaded.state.title}”.`,
        action: { label: 'Undo', onClick: undoTo(previous, previousSession) },
      })
      for (const note of loaded.notes) toast({ tone: 'info', message: note })
    } catch (error) {
      toast({
        tone: 'error',
        message:
          isApiError(error) && error.status === 404
            ? 'That design no longer exists.'
            : isApiError(error) && error.isNetworkError
              ? 'You appear to be offline. Check your connection and try again.'
              : 'We couldn’t open that design. Please try again.',
      })
    } finally {
      setOpeningId(null)
    }
  }

  const handleDesignDeleted = (designId: string) => {
    if (designId !== session.designId) return
    // The wall on screen was that design: keep it as an unsaved copy rather than losing the work.
    setSession(NEW_DESIGN)
    baseline.current = ''
    toast({
      tone: 'info',
      message: 'That design was deleted. Your wall is still here. Save it to keep a copy.',
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

  const handleQuote = () => {
    if (fitProblem) {
      toast({
        tone: 'error',
        message: `A quote needs a layout that fits the wall. ${fitProblem}`,
        action: { label: 'Fix with Generate', onClick: handleGenerate },
      })
      return
    }
    toast({
      message: 'Quote requests open soon. Save your design now and request a quote from it later.',
      action: { label: 'Save design', onClick: requestSave },
    })
  }

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
    <PhotoLibraryContext value={library}>
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
          onSave={requestSave}
          onQuote={handleQuote}
          saveStatus={saveStatus}
          actionsBlocked={fitProblem !== null}
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
              <FrameInspector state={state} dispatch={dispatch} scene={scene} />
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
            <MobileActionBar
              onQuote={handleQuote}
              blocked={fitProblem !== null}
              hidden={typing}
              {...generate}
            />
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
          currentDesignId={session.designId}
          openingId={openingId}
          onSaveCurrent={requestSave}
          onOpenDesign={(design) => void handleOpenDesign(design)}
          onDeleted={handleDesignDeleted}
        />
        <SaveDesignDialog
          open={dialog === 'save'}
          onClose={close}
          defaultTitle={state.title}
          isExisting={session.designId !== null}
          saving={saving}
          error={saveError}
          onSave={(title, asNew) => void handleSave(title, asNew)}
        />
      </div>
    </PhotoLibraryContext>
  )
}

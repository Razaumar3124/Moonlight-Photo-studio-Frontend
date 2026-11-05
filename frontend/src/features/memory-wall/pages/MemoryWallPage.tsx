import { useEffect, useRef, useState } from 'react'
import { useToast } from '@/components/feedback/toastContext'
import { pageTitle } from '@/config/app'
import { useMediaQuery } from '@/hooks/useMediaQuery'
import { ActionBar } from '../components/ActionBar'
import { CanvasPanel } from '../components/CanvasPanel'
import { AiAssistantPanel, LayoutPanel, WallConfigPanel } from '../components/ConfigPanels'
import { FrameSelectionPanel, PreviewSettingsPanel } from '../components/FramePanels'
import { FullscreenPreviewDialog } from '../components/dialogs/FullscreenPreviewDialog'
import { SaveDesignDialog } from '../components/dialogs/SaveDesignDialog'
import { SavedDesignsDialog } from '../components/dialogs/SavedDesignsDialog'
import { TemplatesDialog } from '../components/dialogs/TemplatesDialog'
import { PlannerHeader } from '../components/PlannerHeader'
import { LAYOUT_STYLES } from '../constants'
import { usePhotoUpload } from '../hooks/usePhotoUpload'
import { usePlanner } from '../hooks/usePlanner'
import { suggestLayouts } from '../lib/geometry/scene'
import type { PlannerState } from '../lib/plannerState'
import { savedDesignsStore } from '../lib/savedDesigns'
import type { PlannerTemplate } from '../lib/templates'

type DialogName = 'fullscreen' | 'templates' | 'saved' | 'save' | null

const styleLabel = (id: string) => LAYOUT_STYLES.find((s) => s.id === id)?.label ?? id

/**
 * Memory Wall Planner. All state lives in usePlanner; this page wires panels, dialogs and
 * toasts. Destructive actions (reset, opening a saved design) offer Undo instead of a confirm.
 */
export default function MemoryWallPage() {
  const { state, dispatch, scene } = usePlanner()
  const toast = useToast()
  const [dialog, setDialog] = useState<DialogName>(null)
  const [generating, setGenerating] = useState(false)
  const svgRef = useRef<SVGSVGElement>(null)
  const isTabletUp = useMediaQuery('(min-width: 48rem)')
  // Page-level, so uploaded photos stay valid for the whole visit (collapsing a panel, Undo).
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
          ? `Best fit: ${styleLabel(best.style)} layout, option ${best.variant + 1}. Covers ${Math.round(best.scene.coverage * 100)}% of the wall.`
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
      message: `“${saved.title}” saved to My Saved Templates.`,
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

  const collapsible = !isTabletUp

  return (
    <div className="min-h-dvh bg-cream-100 pb-24 md:pb-0">
      <title>{pageTitle('Memory Wall Planner')}</title>
      <PlannerHeader onOpenSaved={() => setDialog('saved')} />

      <main className="mx-auto flex max-w-[100rem] flex-col gap-4 px-3 py-4 sm:px-6 lg:px-8 lg:py-6">
        <div className="grid grid-cols-1 items-start gap-4 md:grid-cols-2 xl:grid-cols-[minmax(19rem,22rem)_minmax(0,1fr)_minmax(20rem,24rem)]">
          {/* Centre column first in the DOM on small screens: see the wall before the controls. */}
          <div className="min-w-0 md:col-span-2 xl:order-2 xl:col-span-1">
            <CanvasPanel
              state={state}
              dispatch={dispatch}
              scene={scene}
              svgRef={svgRef}
              generating={generating}
              onSave={() => setDialog('save')}
              onReset={handleReset}
              onGenerate={handleGenerate}
              onRegenerate={() => dispatch({ type: 'layout/regenerate' })}
              onRedesign={() => dispatch({ type: 'layout/redesign' })}
            />
          </div>
          <div className="flex min-w-0 flex-col gap-4 xl:order-1">
            <WallConfigPanel state={state} dispatch={dispatch} collapsible={collapsible} />
            <LayoutPanel state={state} dispatch={dispatch} collapsible={collapsible} />
            <AiAssistantPanel state={state} onApplyTemplate={applyTemplate} collapsible={collapsible} />
          </div>
          <div className="flex min-w-0 flex-col gap-4 xl:order-3">
            <FrameSelectionPanel
              state={state}
              dispatch={dispatch}
              collapsible={collapsible}
              onUpload={uploadPhoto}
            />
            <PreviewSettingsPanel state={state} dispatch={dispatch} />
          </div>
        </div>

        <ActionBar
          onFullscreen={() => setDialog('fullscreen')}
          onTemplates={() => setDialog('templates')}
          onSaved={() => setDialog('saved')}
          onQuote={() =>
            toast({
              message: 'Quote requests open soon. Save your design now and request a quote from it later.',
              action: { label: 'Save design', onClick: () => setDialog('save') },
            })
          }
        />
      </main>

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

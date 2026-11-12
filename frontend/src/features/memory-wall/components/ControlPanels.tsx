import { Eye, Frame as FrameIcon, LayoutDashboard, Ruler, SlidersHorizontal } from 'lucide-react'
import { useEffect, useId, useRef, type Dispatch } from 'react'
import { TabPanel, Tabs } from '@/components/ui/Tabs'
import { cn } from '@/lib/cn'
import type { Scene } from '../lib/geometry/scene'
import type { PlannerAction, PlannerState } from '../lib/plannerState'
import type { PlannerTemplate } from '../lib/templates'
import { AiLayoutsSection, ArrangementSection, WallSection } from './ConfigPanels'
import { FrameInspector, ViewSettings } from './FramePanels'

export type SheetTab = 'wall' | 'layout' | 'frame' | 'view'
export type SidePanelTab = 'setup' | 'frame'

export interface ControlPanelProps {
  state: PlannerState
  dispatch: Dispatch<PlannerAction>
  scene: Scene
  onApplyTemplate: (template: PlannerTemplate) => void
  onOpenTemplates: () => void
}

const divided =
  '[&>section+section]:mt-(--pl-gap) [&>section+section]:border-t [&>section+section]:border-ivory-300 [&>section+section]:pt-(--pl-gap)'

/** Everything in the desktop left rail, stacked (tablet "Set up" tab). */
function SetupSections(p: ControlPanelProps) {
  return (
    <>
      <WallSection state={p.state} dispatch={p.dispatch} />
      <ArrangementSection state={p.state} dispatch={p.dispatch} />
      <AiLayoutsSection
        state={p.state}
        onApplyTemplate={p.onApplyTemplate}
        onOpenTemplates={p.onOpenTemplates}
      />
    </>
  )
}

/** Tablet / landscape: one side panel with "Set up" and "Frame" tabs beside the stage. */
export function SidePanel({
  tab,
  onTabChange,
  className,
  ...p
}: ControlPanelProps & { tab: SidePanelTab; onTabChange: (t: SidePanelTab) => void; className?: string }) {
  const idBase = useId()
  return (
    <aside
      aria-label="Design controls"
      className={cn('flex min-h-0 min-w-0 flex-col border-l border-ivory-300 bg-ivory-50', className)}
    >
      <div className="shrink-0 px-(--pl-pad) pt-(--pl-pad) pb-2">
        <Tabs<SidePanelTab>
          idBase={idBase}
          label="Design controls"
          value={tab}
          onChange={onTabChange}
          tabs={[
            { id: 'setup', label: 'Set up', icon: <SlidersHorizontal aria-hidden /> },
            { id: 'frame', label: `Frame ${p.state.selectedIndex + 1}`, icon: <FrameIcon aria-hidden /> },
          ]}
        />
      </div>
      <div className="relative min-h-0 flex-1 scroll-quiet overflow-y-auto overscroll-contain px-(--pl-pad) pt-2 pb-(--pl-pad)">
        <TabPanel idBase={idBase} id="setup" active={tab === 'setup'} className={divided}>
          <SetupSections {...p} />
        </TabPanel>
        <TabPanel idBase={idBase} id="frame" active={tab === 'frame'} className="min-h-full">
          <FrameInspector state={p.state} dispatch={p.dispatch} scene={p.scene} />
        </TabPanel>
      </div>
    </aside>
  )
}

/**
 * Phones / portrait tablets: a docked sheet under the wall with Wall · Layout · Frame · View
 * tabs. The handle grows it (and shrinks the wall) for longer editing.
 */
export function MobileSheet({
  tab,
  onTabChange,
  expanded,
  onToggleExpanded,
  onTypingChange,
  className,
  ...p
}: ControlPanelProps & {
  tab: SheetTab
  onTabChange: (t: SheetTab) => void
  expanded: boolean
  onToggleExpanded: () => void
  /** A text field has focus (the on-screen keyboard is likely open). */
  onTypingChange: (typing: boolean) => void
  className?: string
}) {
  const idBase = useId()
  const rootRef = useRef<HTMLElement>(null)

  // Text fields open the on-screen keyboard: tell the page, so the bottom bar steps aside.
  useEffect(() => {
    const root = rootRef.current
    if (!root) return
    const isTextField = (el: EventTarget | null) =>
      el instanceof HTMLInputElement && ['text', 'search', 'number', 'email', 'tel'].includes(el.type)
    const onIn = (e: FocusEvent) => isTextField(e.target) && onTypingChange(true)
    const onOut = (e: FocusEvent) => isTextField(e.target) && onTypingChange(false)
    root.addEventListener('focusin', onIn)
    root.addEventListener('focusout', onOut)
    return () => {
      root.removeEventListener('focusin', onIn)
      root.removeEventListener('focusout', onOut)
    }
  }, [onTypingChange])

  return (
    <section
      ref={rootRef}
      aria-label="Design controls"
      className={cn(
        'relative z-10 -mt-3 flex min-h-0 flex-col rounded-t-2xl border-t border-ivory-300 bg-ivory-50 shadow-[0_-10px_30px_-16px_rgb(0_0_0/0.6)]',
        className,
      )}
    >
      <button
        type="button"
        onClick={onToggleExpanded}
        aria-expanded={expanded}
        aria-label={expanded ? 'Show more of the wall' : 'Give the controls more room'}
        className="group mx-auto flex h-5 w-24 shrink-0 items-center justify-center"
      >
        <span
          className={cn(
            'h-1 rounded-full bg-ivory-300 transition-[width,background-color] duration-200 group-hover:bg-charcoal-300',
            expanded ? 'w-6' : 'w-10',
          )}
        />
      </button>
      <div className="shrink-0 px-3 pb-2">
        <Tabs<SheetTab>
          idBase={idBase}
          label="Design controls"
          value={tab}
          onChange={onTabChange}
          tabs={[
            { id: 'wall', label: 'Wall', icon: <Ruler aria-hidden /> },
            { id: 'layout', label: 'Layout', icon: <LayoutDashboard aria-hidden /> },
            { id: 'frame', label: 'Frame', icon: <FrameIcon aria-hidden /> },
            { id: 'view', label: 'View', icon: <Eye aria-hidden /> },
          ]}
        />
      </div>
      <div className="relative min-h-0 flex-1 scroll-quiet overflow-y-auto overscroll-contain px-4 pt-2 pb-4">
        <TabPanel idBase={idBase} id="wall" active={tab === 'wall'}>
          <WallSection state={p.state} dispatch={p.dispatch} />
        </TabPanel>
        <TabPanel idBase={idBase} id="layout" active={tab === 'layout'} className={divided}>
          <ArrangementSection state={p.state} dispatch={p.dispatch} />
          <AiLayoutsSection
            state={p.state}
            onApplyTemplate={p.onApplyTemplate}
            onOpenTemplates={p.onOpenTemplates}
          />
        </TabPanel>
        <TabPanel idBase={idBase} id="frame" active={tab === 'frame'}>
          <FrameInspector state={p.state} dispatch={p.dispatch} scene={p.scene} />
        </TabPanel>
        <TabPanel idBase={idBase} id="view" active={tab === 'view'}>
          <ViewSettings state={p.state} dispatch={p.dispatch} />
        </TabPanel>
      </div>
    </section>
  )
}

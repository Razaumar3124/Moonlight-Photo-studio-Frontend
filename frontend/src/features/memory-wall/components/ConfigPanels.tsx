import { LayoutDashboard, LayoutGrid, Sparkles } from 'lucide-react'
import type { Dispatch } from 'react'
import { Badge } from '@/components/ui/Badge'
import { NumberStepper } from '@/components/ui/NumberStepper'
import { SegmentedControl } from '@/components/ui/SegmentedControl'
import { SwatchPicker } from '@/components/ui/SwatchPicker'
import { cn } from '@/lib/cn'
import { roundTo, type LengthUnit } from '@/lib/units'
import {
  AI_LAYOUT_PRESETS,
  GAP_UNITS,
  LAYOUT_STYLES,
  PAINT_SHADES,
  PLANNER_RULES,
  WALL_UNITS,
  type GapUnit,
  type LayoutStyleId,
} from '../constants'
import type { PlannerAction, PlannerState } from '../lib/plannerState'
import { findTemplate, type PlannerTemplate } from '../lib/templates'
import { DimensionInput } from './DimensionInput'
import { StepCard } from './StepCard'

interface PanelProps {
  state: PlannerState
  dispatch: Dispatch<PlannerAction>
  collapsible?: boolean
}

/* ① Wall Configuration */
export function WallConfigPanel({ state, dispatch, collapsible }: PanelProps) {
  const paint = PAINT_SHADES.find((p) => p.id === state.wall.paintId)
  return (
    <StepCard
      step={1}
      title="Wall Configuration"
      subtitle="Set up your wall dimensions and layout preferences."
      collapsible={collapsible}
    >
      <div className="grid grid-cols-2 gap-3">
        <DimensionInput
          label="Wall Width"
          valueIn={state.wall.widthIn}
          unit={state.displayUnit}
          minIn={PLANNER_RULES.wallWidthIn.min}
          maxIn={PLANNER_RULES.wallWidthIn.max}
          onCommit={(value) => dispatch({ type: 'wall/setSize', dimension: 'widthIn', value })}
        />
        <DimensionInput
          label="Wall Height"
          valueIn={state.wall.heightIn}
          unit={state.displayUnit}
          minIn={PLANNER_RULES.wallHeightIn.min}
          maxIn={PLANNER_RULES.wallHeightIn.max}
          onCommit={(value) => dispatch({ type: 'wall/setSize', dimension: 'heightIn', value })}
        />
      </div>
      <SwatchPicker
        label="Paint Shade"
        options={PAINT_SHADES}
        value={state.wall.paintId}
        onChange={(paintId) => dispatch({ type: 'wall/setPaint', paintId })}
        aside={paint?.label}
      />
      <SegmentedControl<LengthUnit>
        label="Measurement Unit"
        showLabel
        options={WALL_UNITS.map((u) => ({ value: u, label: u }))}
        value={state.displayUnit}
        onChange={(unit) => dispatch({ type: 'unit/set', unit })}
      />
    </StepCard>
  )
}

const STYLE_ICONS: Partial<Record<LayoutStyleId, React.ReactNode>> = {
  grid: <LayoutGrid aria-hidden />,
  salon: <LayoutDashboard aria-hidden />,
}

/* ② Layout */
export function LayoutPanel({ state, dispatch, collapsible }: PanelProps) {
  const { gapIn, gapUnit } = state.layout
  const inCm = gapUnit === 'cm'
  const shown = inCm ? roundTo(gapIn * 2.54, 1) : gapIn
  return (
    <StepCard step={2} title="Layout" collapsible={collapsible}>
      <SegmentedControl<LayoutStyleId>
        label="Layout style"
        options={LAYOUT_STYLES.map((s) => ({ value: s.id, label: s.label, icon: STYLE_ICONS[s.id] }))}
        value={state.layout.style}
        onChange={(style) => dispatch({ type: 'layout/setStyle', style })}
      />
      <div className="flex flex-col gap-2">
        <span className="text-sm font-semibold text-ink-900">Frame Gaps</span>
        <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] items-center gap-3">
          <NumberStepper
            label="Frame gap"
            hideLabel
            value={shown}
            min={0}
            max={inCm ? roundTo(PLANNER_RULES.gapIn.max * 2.54, 0) : PLANNER_RULES.gapIn.max}
            step={inCm ? 1 : 0.5}
            precision={1}
            onChange={(v) => dispatch({ type: 'layout/setGap', gapIn: inCm ? v / 2.54 : v })}
          />
          <SegmentedControl<GapUnit>
            label="Gap unit"
            size="sm"
            options={GAP_UNITS.map((u) => ({ value: u, label: u }))}
            value={gapUnit}
            onChange={(unit) => dispatch({ type: 'layout/setGapUnit', unit })}
          />
        </div>
      </div>
      <NumberStepper
        label="Number of Frames"
        value={state.frames.length}
        min={PLANNER_RULES.frameCount.min}
        max={PLANNER_RULES.frameCount.max}
        step={1}
        precision={0}
        onChange={(count) => dispatch({ type: 'frames/setCount', count })}
      />
    </StepCard>
  )
}

/* ✦ AI Layout Assistant */
export function AiAssistantPanel({
  state,
  onApplyTemplate,
  collapsible,
}: Omit<PanelProps, 'dispatch'> & { onApplyTemplate: (template: PlannerTemplate) => void }) {
  return (
    <StepCard
      icon={<Sparkles />}
      title="AI Layout Assistant"
      subtitle="Generate beautiful arrangements based on your wall dimensions and frame selection."
      badge={<Badge tone="new">New</Badge>}
      collapsible={collapsible}
    >
      <ul className="grid grid-cols-4 gap-2">
        {AI_LAYOUT_PRESETS.map((preset) => {
          const active = state.templateId === preset.templateId
          return (
            <li key={preset.templateId}>
              <button
                type="button"
                aria-pressed={active}
                onClick={() => {
                  const template = findTemplate(preset.templateId)
                  if (template) onApplyTemplate(template)
                }}
                className="group flex w-full flex-col items-center gap-1.5 rounded-xl p-1 text-center"
              >
                <span
                  className={cn(
                    'block w-full overflow-hidden rounded-lg border-2 transition-[border-color,transform,box-shadow] group-hover:-translate-y-0.5 group-hover:shadow-card',
                    active ? 'border-brand-600 shadow-card' : 'border-cream-300',
                  )}
                >
                  <img
                    src={preset.thumbnail.src}
                    width={preset.thumbnail.width}
                    height={preset.thumbnail.height}
                    alt=""
                    loading="lazy"
                    decoding="async"
                    className="aspect-[349/284] w-full object-cover"
                  />
                </span>
                <span
                  className={cn(
                    'text-[0.6875rem] leading-tight sm:text-xs',
                    active ? 'font-semibold text-brand-700' : 'text-ink-700',
                  )}
                >
                  {preset.label}
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </StepCard>
  )
}

import { ArrowRight, Check, CircleAlert, Sparkles } from 'lucide-react'
import { useId, useMemo, type Dispatch } from 'react'
import { NumberStepper } from '@/components/ui/NumberStepper'
import { SegmentedControl } from '@/components/ui/SegmentedControl'
import { SwatchPicker } from '@/components/ui/SwatchPicker'
import { cn } from '@/lib/cn'
import { roundTo, type LengthUnit } from '@/lib/units'
import {
  AI_LAYOUT_PRESETS,
  GAP_UNITS,
  PAINT_SHADES,
  PLANNER_RULES,
  WALL_UNITS,
  type GapUnit,
} from '../constants'
import { buildScene } from '../lib/geometry/scene'
import { plannerReducer, type PlannerAction, type PlannerState } from '../lib/plannerState'
import { findTemplate, type PlannerTemplate } from '../lib/templates'
import { DimensionInput } from './DimensionInput'
import { RailSection } from './RailSection'

interface SectionProps {
  state: PlannerState
  dispatch: Dispatch<PlannerAction>
}

const rowLabel = 'text-[0.8125rem] font-semibold text-charcoal-700'

/* 01 · The Wall */
export function WallSection({ state, dispatch }: SectionProps) {
  const paint = PAINT_SHADES.find((p) => p.id === state.wall.paintId)
  return (
    <RailSection numeral="01" title="The Wall">
      <div className="grid grid-cols-2 gap-2">
        <DimensionInput
          compact
          label="Wall width"
          valueIn={state.wall.widthIn}
          unit={state.displayUnit}
          minIn={PLANNER_RULES.wallWidthIn.min}
          maxIn={PLANNER_RULES.wallWidthIn.max}
          onCommit={(value) => dispatch({ type: 'wall/setSize', dimension: 'widthIn', value })}
        />
        <DimensionInput
          compact
          label="Wall height"
          valueIn={state.wall.heightIn}
          unit={state.displayUnit}
          minIn={PLANNER_RULES.wallHeightIn.min}
          maxIn={PLANNER_RULES.wallHeightIn.max}
          onCommit={(value) => dispatch({ type: 'wall/setSize', dimension: 'heightIn', value })}
        />
      </div>
      <div className="flex items-center justify-between gap-3">
        <span aria-hidden className={rowLabel}>
          Units
        </span>
        <SegmentedControl<LengthUnit>
          label="Measurement unit"
          appearance="neutral"
          size="xs"
          options={WALL_UNITS.map((u) => ({ value: u, label: u }))}
          value={state.displayUnit}
          onChange={(unit) => dispatch({ type: 'unit/set', unit })}
          className="w-[11rem]"
        />
      </div>
      <SwatchPicker
        size="sm"
        label="Paint shade"
        options={PAINT_SHADES}
        value={state.wall.paintId}
        onChange={(paintId) => dispatch({ type: 'wall/setPaint', paintId })}
        aside={paint?.label}
      />
    </RailSection>
  )
}

/* 02 · Arrangement */
export function ArrangementSection({ state, dispatch }: SectionProps) {
  const { gapIn, gapUnit } = state.layout
  const inCm = gapUnit === 'cm'
  const shown = inCm ? roundTo(gapIn * 2.54, 1) : gapIn
  return (
    <RailSection numeral="02" title="Arrangement">
      <NumberStepper
        size="sm"
        label="Frames"
        value={state.frames.length}
        min={PLANNER_RULES.frameCount.min}
        max={PLANNER_RULES.frameCount.max}
        step={1}
        precision={0}
        onChange={(count) => dispatch({ type: 'frames/setCount', count })}
      />
      <div className="flex items-center justify-between gap-2">
        <span aria-hidden className={cn(rowLabel, 'whitespace-nowrap')}>
          <span className="dense:hidden">Frame gap</span>
          <span className="hidden dense:inline">Gap</span>
        </span>
        <div className="flex min-w-0 items-center justify-end gap-1.5">
          <NumberStepper
            size="sm"
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
            appearance="neutral"
            size="xs"
            options={GAP_UNITS.map((u) => ({ value: u, label: u }))}
            value={gapUnit}
            onChange={(unit) => dispatch({ type: 'layout/setGapUnit', unit })}
            className="w-[4.75rem] min-w-[3.75rem] shrink"
          />
        </div>
      </div>
    </RailSection>
  )
}

/* ✦ AI Layouts */
export function AiLayoutsSection({
  state,
  onApplyTemplate,
  onOpenTemplates,
}: {
  state: PlannerState
  onApplyTemplate: (template: PlannerTemplate) => void
  onOpenTemplates: () => void
}) {
  const hintId = useId()
  // Would each preset fit THIS wall? Same check as the template gallery (4 scene builds).
  const fits = useMemo(
    () =>
      Object.fromEntries(
        AI_LAYOUT_PRESETS.map((p) => {
          const template = findTemplate(p.templateId)
          if (!template) return [p.templateId, true]
          const next = plannerReducer(state, { type: 'template/apply', template, templateId: template.id })
          return [p.templateId, buildScene(next).fits]
        }),
      ) as Record<string, boolean>,
    [state],
  )

  return (
    <RailSection
      numeral={<Sparkles aria-hidden className="size-3.5 text-champagne-400" />}
      title="AI Layouts"
      aside={
        <button
          type="button"
          onClick={onOpenTemplates}
          className="-my-1 inline-flex items-center gap-1 rounded-md px-1 py-1 text-xs font-semibold text-charcoal-700 transition-colors hover:text-brand-700"
        >
          All templates <ArrowRight aria-hidden className="size-3.5" />
        </button>
      }
    >
      <p id={hintId} className="-mt-1 hidden text-xs leading-snug text-charcoal-500 roomy:block">
        Curated arrangements for your wall. Your photos stay in place.
      </p>
      <ul className="grid grid-cols-2 gap-2" aria-describedby={hintId}>
        {AI_LAYOUT_PRESETS.map((preset) => {
          const active = state.templateId === preset.templateId
          const fitsWall = fits[preset.templateId] ?? true
          return (
            <li key={preset.templateId}>
              <button
                type="button"
                aria-pressed={active}
                aria-label={`${preset.label}${fitsWall ? '' : ' (may not fit this wall)'}`}
                onClick={() => {
                  const template = findTemplate(preset.templateId)
                  if (template) onApplyTemplate(template)
                }}
                className="group flex w-full flex-col gap-1 rounded-lg text-left"
              >
                <span
                  className={cn(
                    'relative block w-full overflow-hidden rounded-lg ring-1 transition-[box-shadow,transform] duration-200 group-hover:-translate-y-0.5 group-hover:shadow-[0_8px_18px_-10px_rgb(31_27_25/0.5)]',
                    active ? 'ring-2 ring-brand-600 ring-offset-2 ring-offset-ivory-50' : 'ring-black/8',
                  )}
                >
                  <img
                    src={preset.thumbnail.src}
                    srcSet={preset.thumbnail.srcSet}
                    sizes="(min-width: 80rem) 10rem, 45vw"
                    width={preset.thumbnail.width}
                    height={preset.thumbnail.height}
                    alt=""
                    loading="lazy"
                    decoding="async"
                    className="aspect-[16/10] w-full object-cover transition-transform duration-300 group-hover:scale-[1.03] dense:aspect-[5/2]"
                  />
                  {active && (
                    <span className="absolute top-1.5 right-1.5 grid size-5 place-items-center rounded-full bg-brand-600 text-white shadow-md">
                      <Check aria-hidden className="size-3" strokeWidth={3} />
                    </span>
                  )}
                  {!fitsWall && (
                    <span className="absolute bottom-1.5 left-1.5 inline-flex items-center gap-1 rounded-full bg-ivory-50/95 px-1.5 py-0.5 text-[0.625rem] font-semibold text-gold-600 shadow-sm">
                      <CircleAlert aria-hidden className="size-3" /> Too big
                    </span>
                  )}
                </span>
                <span
                  className={cn(
                    'truncate px-0.5 text-xs',
                    active ? 'font-semibold text-brand-700' : 'font-medium text-charcoal-700',
                  )}
                >
                  {preset.label}
                </span>
              </button>
            </li>
          )
        })}
      </ul>
    </RailSection>
  )
}

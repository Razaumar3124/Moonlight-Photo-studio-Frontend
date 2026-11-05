import { CircleAlert, CircleCheck } from 'lucide-react'
import { useMemo, useState } from 'react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Dialog } from '@/components/ui/Dialog'
import { SegmentedControl } from '@/components/ui/SegmentedControl'
import { cn } from '@/lib/cn'
import { formatLength } from '@/lib/units'
import { LAYOUT_STYLES, PLANNER_RULES, type LayoutStyleId } from '../../constants'
import { buildScene } from '../../lib/geometry/scene'
import { plannerReducer, type PlannerState } from '../../lib/plannerState'
import { TEMPLATE_CATEGORIES, TEMPLATES, type PlannerTemplate } from '../../lib/templates'
import { WallSvg } from '../WallSvg'

interface TemplatesDialogProps {
  open: boolean
  onClose: () => void
  state: PlannerState
  onApply: (template: PlannerTemplate) => void
}

/**
 * Template gallery. Every preview is computed live by the same geometry engine on the
 * user's own wall (size + paint), and tells them whether it fits before they apply it.
 */
export function TemplatesDialog({ open, onClose, state, onApply }: TemplatesDialogProps) {
  const [category, setCategory] = useState<'all' | LayoutStyleId>('all')
  const visible = TEMPLATES.filter((t) => category === 'all' || t.style === category)

  return (
    <Dialog
      open={open}
      onClose={onClose}
      size="lg"
      title="All Templates"
      description="Curated arrangements, previewed on your wall. Your photos stay in place when you switch."
    >
      <SegmentedControl
        label="Filter by layout"
        options={TEMPLATE_CATEGORIES.map((c) => ({ value: c.value, label: c.label }))}
        value={category}
        onChange={setCategory}
        size="sm"
        className="mb-5 max-w-xl"
      />
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {visible.map((t) => (
          <li key={t.id}>
            <TemplateCard
              template={t}
              state={state}
              active={state.templateId === t.id}
              onApply={() => onApply(t)}
            />
          </li>
        ))}
      </ul>
    </Dialog>
  )
}

function TemplateCard({
  template,
  state,
  active,
  onApply,
}: {
  template: PlannerTemplate
  state: PlannerState
  active: boolean
  onApply: () => void
}) {
  // Same wall AND same sofa setting as the planner, so "Fits your wall" here means it fits there.
  const scene = useMemo(() => {
    const preview: PlannerState = { ...state, fillWithSamples: true }
    return buildScene(plannerReducer(preview, { type: 'template/apply', template, templateId: template.id }))
  }, [template, state])
  const unit = state.displayUnit
  const codes = new Set(scene.warnings.map((w) => w.code))
  const needW = scene.arrangement.w + 2 * PLANNER_RULES.wallMarginIn
  const fitLabel = codes.has('TOO_WIDE')
    ? `Needs ≥ ${formatLength(needW, unit)} wide`
    : codes.has('TOO_TALL')
      ? 'Too tall for this wall'
      : 'Check fit'
  const style = LAYOUT_STYLES.find((s) => s.id === template.style)?.label

  return (
    <article
      className={cn(
        'group flex h-full flex-col overflow-hidden rounded-xl border bg-white shadow-field transition-[box-shadow,transform,border-color] hover:-translate-y-0.5 hover:shadow-card',
        active ? 'border-brand-600 ring-2 ring-brand-600/20' : 'border-cream-300',
      )}
    >
      <div className="bg-cream-200 p-2">
        <WallSvg
          scene={scene}
          detail="low"
          className="aspect-[4/3] w-full rounded-lg"
          title={`${template.name} preview`}
        />
      </div>
      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="flex items-start justify-between gap-2">
          <h3 className="font-display text-lg font-semibold text-ink-900">{template.name}</h3>
          {active && <Badge tone="brand">In use</Badge>}
        </div>
        <p className="text-sm text-ink-500">{template.description}</p>
        <p className="text-xs text-ink-500">
          {template.frames.length} frames · {style}
        </p>
        <div className="mt-auto flex items-center justify-between gap-2 pt-2">
          {scene.fits ? (
            <Badge tone="success">
              <CircleCheck aria-hidden /> Fits your wall
            </Badge>
          ) : (
            <Badge tone="warning">
              <CircleAlert aria-hidden /> {fitLabel}
            </Badge>
          )}
          <Button size="md" className="h-9" onClick={onApply} disabled={active}>
            {active ? 'Applied' : 'Use template'}
          </Button>
        </div>
      </div>
    </article>
  )
}

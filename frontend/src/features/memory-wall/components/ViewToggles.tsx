import type { Dispatch } from 'react'
import { Tooltip } from '@/components/ui/IconButton'
import { cn } from '@/lib/cn'
import type { PlannerAction, PlannerState } from '../lib/plannerState'
import { PREVIEW_OPTIONS } from '../lib/previewOptions'

/** Icon toggle group (aria-pressed) for the stage toolbar (`stage`) or a light header (`light`). */
export function ViewToggles({
  state,
  dispatch,
  tone,
  className,
}: {
  state: PlannerState
  dispatch: Dispatch<PlannerAction>
  tone: 'stage' | 'light'
  className?: string
}) {
  return (
    <div
      role="group"
      aria-label="View options"
      className={cn(
        'flex items-center gap-0.5 rounded-lg p-0.5',
        tone === 'stage' ? 'bg-white/[0.06] ring-1 ring-white/10' : 'bg-ivory-200',
        className,
      )}
    >
      {PREVIEW_OPTIONS.map((opt) => {
        const pressed = state.preview[opt.key]
        return (
          <button
            key={opt.key}
            type="button"
            aria-label={opt.short}
            aria-pressed={pressed}
            onClick={() => dispatch({ type: 'preview/toggle', key: opt.key, value: !pressed })}
            className={cn(
              'group/ib relative grid size-[calc(var(--pl-ctl,2.25rem)-0.25rem)] place-items-center rounded-md transition-colors duration-150 [&>svg]:size-4',
              tone === 'stage'
                ? pressed
                  ? 'bg-ivory-50 text-charcoal-900 shadow-thumb'
                  : 'text-ivory-100/60 hover:bg-white/10 hover:text-white'
                : pressed
                  ? 'bg-white text-charcoal-900 shadow-thumb'
                  : 'text-charcoal-500 hover:text-charcoal-900',
            )}
          >
            {opt.icon}
            <Tooltip side="bottom">
              {opt.short}: {pressed ? 'on' : 'off'}
            </Tooltip>
          </button>
        )
      })}
    </div>
  )
}

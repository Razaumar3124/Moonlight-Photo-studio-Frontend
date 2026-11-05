import { CircleAlert, CircleCheck, Info, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '@/lib/cn'

type AlertTone = 'info' | 'error' | 'success'

const tones: Record<AlertTone, { box: string; icon: LucideIcon }> = {
  info: { box: 'border-gold-200 bg-gold-100/60 text-ink-700', icon: Info },
  error: { box: 'border-brand-200 bg-brand-50 text-brand-800', icon: CircleAlert },
  success: { box: 'border-success-500/30 bg-success-50 text-ink-900', icon: CircleCheck },
}

interface AlertProps {
  tone?: AlertTone
  children: ReactNode
  className?: string
}

/**
 * Inline, non-blocking message. `error` is announced immediately (role="alert");
 * `info`/`success` politely (role="status").
 */
export function Alert({ tone = 'info', children, className }: AlertProps) {
  const { box, icon: Icon } = tones[tone]
  return (
    <div
      role={tone === 'error' ? 'alert' : 'status'}
      className={cn('flex items-start gap-2.5 rounded-field border px-3.5 py-3 text-sm', box, className)}
    >
      <Icon aria-hidden className="mt-px size-4.5 shrink-0" />
      <div className="min-w-0">{children}</div>
    </div>
  )
}

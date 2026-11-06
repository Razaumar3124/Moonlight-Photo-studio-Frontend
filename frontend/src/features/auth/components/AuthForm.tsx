import type { FormEventHandler, ReactNode } from 'react'
import { Alert } from '@/components/feedback/Alert'
import { Button, type ButtonProps } from '@/components/ui/Button'
import { Divider } from '@/components/ui/Divider'
import { cn } from '@/lib/cn'
import { GoogleSignIn } from './GoogleSignIn'

interface AuthFormProps {
  /** Accessible name of the form landmark, e.g. "Sign in". */
  label: string
  onSubmit: FormEventHandler<HTMLFormElement>
  formError: string | null
  submitting: boolean
  submitLabel: string
  /** Button text while submitting, e.g. "Signing in…". */
  submittingLabel: string
  submitVariant?: Extract<ButtonProps['variant'], 'primary' | 'primary-gradient'>
  /** Tighter spacing for longer forms (Register). */
  compact?: boolean
  /** The fields. */
  children: ReactNode
}

/**
 * Shared skeleton of the auth forms (mockups): form-level error → fields → primary CTA →
 * "OR" → Continue with Google. Login and Register only provide their fields and labels.
 */
export function AuthForm({
  label,
  onSubmit,
  formError,
  submitting,
  submitLabel,
  submittingLabel,
  submitVariant = 'primary',
  compact = false,
  children,
}: AuthFormProps) {
  return (
    // Gaps: full-size classes, or the height-aware `--auth-*` values on auth-fluid viewports.
    <div className={cn('flex flex-col auth-fluid:gap-[var(--auth-stack-gap)]', compact ? 'gap-5' : 'gap-6')}>
      <form
        noValidate
        onSubmit={onSubmit}
        aria-label={label}
        className={cn('flex flex-col auth-fluid:gap-[var(--auth-form-gap)]', compact ? 'gap-4' : 'gap-5')}
      >
        {formError && <Alert tone="error">{formError}</Alert>}
        {children}
        <Button
          type="submit"
          variant={submitVariant}
          size="lg"
          fullWidth
          loading={submitting}
          loadingText={submittingLabel}
          className="mt-1 auth-fluid:mt-[var(--auth-cta-gap)]"
        >
          {submitLabel}
        </Button>
      </form>

      <Divider label="Or" />

      <GoogleSignIn />
    </div>
  )
}

import { KeyRound, Mail } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Alert } from '@/components/feedback/Alert'
import { PasswordField } from '@/components/ui/PasswordField'
import { TextField } from '@/components/ui/TextField'
import { ROUTES } from '@/config/routes'
import { useForm } from '@/hooks/useForm'
import { isApiError } from '@/services/apiClient'
import { authService } from '@/services/authService'
import { useCooldown } from '../hooks/useCooldown'
import { AUTH_LIMITS } from '../lib/limits'
import { PASSWORD_HINT } from '../lib/registerValidation'
import {
  CODE_STEP_FIELDS,
  EMAIL_STEP_FIELDS,
  mapCodeStepError,
  mapEmailStepError,
  mapPasswordStepError,
  OTP_LENGTH,
  PASSWORD_STEP_FIELDS,
  sanitizeOtp,
  validateCodeStep,
  validateEmailStep,
  validatePasswordStep,
} from '../lib/resetValidation'
import { AuthForm } from './AuthForm'
import type { ResetStep } from '../lib/resetSteps'

const linkButton =
  'rounded-sm font-semibold text-brand-600 underline decoration-brand-600/40 underline-offset-3 ' +
  'transition-colors hover:text-brand-700 hover:decoration-brand-700 disabled:cursor-not-allowed ' +
  'disabled:text-ink-500 disabled:no-underline'

/**
 * Forgot-password in three steps: email → 6-digit code → new password.
 *
 * - The server answers step 1 identically whether or not the account exists, and so do we:
 *   "if an account exists, a code was sent".
 * - The email and the single-use reset token live in this component's state only (memory),
 *   never in storage, the URL or logs.
 * - Resend is throttled by the cooldown the server reports (and enforces).
 */
export function ForgotPasswordFlow({ onStepChange }: { onStepChange: (step: ResetStep) => void }) {
  const [step, setStepState] = useState<ResetStep>('email')
  const [email, setEmail] = useState('')
  const [resetToken, setResetToken] = useState('')
  const cooldown = useCooldown()

  const setStep = (next: ResetStep) => {
    setStepState(next)
    onStepChange(next)
  }
  const startOver = () => {
    setResetToken('')
    setStep('email')
  }

  if (step === 'email') {
    return (
      <EmailStep
        initialEmail={email}
        onSent={(sentTo, cooldownSeconds) => {
          setEmail(sentTo)
          cooldown.start(cooldownSeconds)
          setStep('code')
        }}
      />
    )
  }
  if (step === 'code') {
    return (
      <CodeStep
        email={email}
        resendIn={cooldown.remaining}
        onResent={cooldown.start}
        onChangeEmail={startOver}
        onVerified={(token) => {
          setResetToken(token)
          setStep('password')
        }}
      />
    )
  }
  return <PasswordStep resetToken={resetToken} onStartOver={startOver} />
}

/* --------------------------------- Step 1 --------------------------------- */

function EmailStep({
  initialEmail,
  onSent,
}: {
  initialEmail: string
  onSent: (email: string, cooldownSeconds: number) => void
}) {
  const { field, handleSubmit, submitting, formError } = useForm({
    fields: EMAIL_STEP_FIELDS,
    initialValues: { email: initialEmail },
    validateField: (f, value) => validateEmailStep(f, value),
    mapSubmitError: mapEmailStepError,
    onSubmit: async (values, signal) => {
      const email = values.email.trim().toLowerCase()
      const res = await authService.forgotPassword({ email }, signal)
      onSent(email, res.cooldown_seconds)
    },
  })

  return (
    <AuthForm
      label="Request a verification code"
      onSubmit={handleSubmit}
      formError={formError}
      submitting={submitting}
      submitLabel="Send Code"
      submittingLabel="Sending code…"
      showGoogle={false}
    >
      <TextField
        {...field('email')}
        label="Email Address"
        placeholder="Enter your email address"
        leftIcon={<Mail />}
        type="email"
        inputMode="email"
        required
        maxLength={AUTH_LIMITS.email}
        autoComplete="email"
        autoCapitalize="none"
        autoCorrect="off"
        spellCheck={false}
        enterKeyHint="go"
      />
    </AuthForm>
  )
}

/* --------------------------------- Step 2 --------------------------------- */

function CodeStep({
  email,
  resendIn,
  onResent,
  onChangeEmail,
  onVerified,
}: {
  email: string
  resendIn: number
  onResent: (cooldownSeconds: number) => void
  onChangeEmail: () => void
  onVerified: (resetToken: string) => void
}) {
  const [resendState, setResendState] = useState<{ tone: 'success' | 'error'; text: string } | null>(null)
  const [resending, setResending] = useState(false)

  const { field, handleSubmit, submitting, formError } = useForm({
    fields: CODE_STEP_FIELDS,
    initialValues: { otp: '' },
    validateField: (f, value) => validateCodeStep(f, value),
    mapSubmitError: mapCodeStepError,
    onSubmit: async (values, signal) => {
      const res = await authService.verifyResetCode({ email, otp: values.otp }, signal)
      onVerified(res.reset_token)
    },
  })

  const resend = async () => {
    if (resending || resendIn > 0) return
    setResending(true)
    setResendState(null)
    try {
      const res = await authService.forgotPassword({ email })
      onResent(res.cooldown_seconds)
      setResendState({ tone: 'success', text: 'A new code is on its way. Older codes no longer work.' })
    } catch (error) {
      if (isApiError(error) && error.status === 429) onResent(30)
      setResendState({
        tone: 'error',
        text:
          isApiError(error) && error.isNetworkError
            ? error.message
            : isApiError(error) && error.status === 429
              ? 'Please wait a little before requesting another code.'
              : 'We couldn’t send a new code right now. Please try again shortly.',
      })
    } finally {
      setResending(false)
    }
  }

  const otp = field('otp')

  return (
    <AuthForm
      label="Enter your verification code"
      onSubmit={handleSubmit}
      formError={formError}
      submitting={submitting}
      submitLabel="Verify Code"
      submittingLabel="Checking…"
      showGoogle={false}
      footer={
        <div className="flex flex-col items-center gap-3 text-center text-sm text-ink-700">
          {resendState && <Alert tone={resendState.tone}>{resendState.text}</Alert>}
          <p>
            Didn’t get it?{' '}
            <button
              type="button"
              onClick={resend}
              disabled={resendIn > 0 || resending}
              className={linkButton}
            >
              {resending ? 'Sending…' : resendIn > 0 ? `Resend code in ${resendIn}s` : 'Resend code'}
            </button>
          </p>
          <button type="button" onClick={onChangeEmail} className={linkButton}>
            Use a different email
          </button>
        </div>
      }
    >
      <Alert tone="info">
        If an account exists for <strong className="font-semibold break-all">{email}</strong>, we’ve sent a{' '}
        {OTP_LENGTH}-digit code. It expires in a few minutes.
      </Alert>
      <TextField
        {...otp}
        onChange={(event) => {
          event.target.value = sanitizeOtp(event.target.value)
          otp.onChange(event)
        }}
        label="Verification Code"
        placeholder="6-digit code"
        leftIcon={<KeyRound />}
        type="text"
        inputMode="numeric"
        required
        maxLength={OTP_LENGTH + 4}
        autoComplete="one-time-code"
        autoCorrect="off"
        spellCheck={false}
        enterKeyHint="go"
        inputClassName="tracking-[0.3em] placeholder:tracking-normal"
      />
    </AuthForm>
  )
}

/* --------------------------------- Step 3 --------------------------------- */

function PasswordStep({ resetToken, onStartOver }: { resetToken: string; onStartOver: () => void }) {
  const navigate = useNavigate()

  const { field, handleSubmit, submitting, formError } = useForm({
    fields: PASSWORD_STEP_FIELDS,
    initialValues: { password: '', confirm: '' },
    validateField: validatePasswordStep,
    mapSubmitError: mapPasswordStepError,
    onSubmit: async (values, signal) => {
      await authService.resetPassword({ reset_token: resetToken, new_password: values.password }, signal)
      // The server revoked every session; sign in again with the new password.
      navigate(ROUTES.login, { replace: true, state: { passwordReset: true } })
    },
  })

  return (
    <AuthForm
      label="Choose a new password"
      onSubmit={handleSubmit}
      formError={formError}
      submitting={submitting}
      submitLabel="Reset Password"
      submittingLabel="Resetting…"
      showGoogle={false}
      footer={
        <p className="text-center text-sm">
          <button type="button" onClick={onStartOver} className={linkButton}>
            Start over
          </button>
        </p>
      }
    >
      <PasswordField
        {...field('password')}
        label="New Password"
        placeholder="Create a new password"
        hint={PASSWORD_HINT}
        required
        maxLength={AUTH_LIMITS.password}
        autoComplete="new-password"
        enterKeyHint="next"
      />
      <PasswordField
        {...field('confirm')}
        label="Confirm Password"
        placeholder="Re-enter your new password"
        required
        maxLength={AUTH_LIMITS.password}
        autoComplete="new-password"
        enterKeyHint="go"
      />
    </AuthForm>
  )
}

import { useState } from 'react'
import { authAssets } from '@/assets/auth'
import { pageTitle } from '@/config/app'
import { ROUTES } from '@/config/routes'
import { AuthHeader } from '../components/AuthHeader'
import { AuthLayout } from '../components/AuthLayout'
import { AuthSwitchPrompt } from '../components/AuthSwitchPrompt'
import { ForgotPasswordFlow } from '../components/ForgotPasswordFlow'
import { RESET_STEP_COPY, type ResetStep } from '../lib/resetSteps'

/** Password recovery: email → verification code → new password (POST /auth/forgot-password/*). */
export default function ForgotPasswordPage() {
  const [step, setStep] = useState<ResetStep>('email')
  const copy = RESET_STEP_COPY[step]

  return (
    <AuthLayout hero={authAssets.login.hero} variant="login">
      <title>{pageTitle('Reset password')}</title>
      <div className="flex flex-col gap-8 auth-fluid:gap-[var(--auth-page-gap)]">
        <AuthHeader title={copy.title} subtitle={copy.subtitle} />
        <ForgotPasswordFlow onStepChange={setStep} />
        <AuthSwitchPrompt prompt="Remembered it?" linkLabel="Back to sign in" to={ROUTES.login} />
      </div>
    </AuthLayout>
  )
}

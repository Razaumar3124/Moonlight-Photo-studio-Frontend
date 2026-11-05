import { authAssets } from '@/assets/auth'
import { Alert } from '@/components/feedback/Alert'
import { pageTitle } from '@/config/app'
import { ROUTES } from '@/config/routes'
import { AuthHeader } from '../components/AuthHeader'
import { AuthLayout } from '../components/AuthLayout'
import { AuthSwitchPrompt } from '../components/AuthSwitchPrompt'

/**
 * Placeholder target for "Forgot Password?" until POST /auth/forgot-password exists (M3).
 * The reset form is built when the backend endpoint lands.
 */
export default function ForgotPasswordPage() {
  return (
    <AuthLayout hero={authAssets.login.hero} variant="login">
      <title>{pageTitle('Reset password')}</title>
      <div className="flex flex-col gap-8">
        <AuthHeader title="Reset Password" subtitle="We’ll help you get back to your memories." />
        <Alert tone="info">
          Online password reset is coming soon. Until then, please contact the studio and we’ll help you
          regain access.
        </Alert>
        <AuthSwitchPrompt prompt="Remembered it?" linkLabel="Back to sign in" to={ROUTES.login} />
      </div>
    </AuthLayout>
  )
}

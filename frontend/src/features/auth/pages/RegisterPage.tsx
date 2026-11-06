import { authAssets } from '@/assets/auth'
import { pageTitle } from '@/config/app'
import { ROUTES } from '@/config/routes'
import { AuthHeader } from '../components/AuthHeader'
import { AuthLayout } from '../components/AuthLayout'
import { AuthSwitchPrompt } from '../components/AuthSwitchPrompt'
import { RegisterForm } from '../components/RegisterForm'

export default function RegisterPage() {
  return (
    <AuthLayout hero={authAssets.register.hero} variant="register" compact>
      <title>{pageTitle('Create account')}</title>
      <div className="flex flex-col gap-6 auth-fluid:gap-[var(--auth-page-gap)]">
        <AuthHeader
          title="Create Your Account"
          subtitle="Join Moonlight and start preserving your favourite memories."
          align="center"
          titleTone="brand"
          compact
        />
        <RegisterForm />
        <AuthSwitchPrompt prompt="Already have an account?" linkLabel="Sign in" to={ROUTES.login} />
      </div>
    </AuthLayout>
  )
}

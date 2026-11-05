import { authAssets } from '@/assets/auth'
import { pageTitle } from '@/config/app'
import { ROUTES } from '@/config/routes'
import { AuthHeader } from '../components/AuthHeader'
import { AuthLayout } from '../components/AuthLayout'
import { AuthSwitchPrompt } from '../components/AuthSwitchPrompt'
import { LoginForm } from '../components/LoginForm'

export default function LoginPage() {
  return (
    <AuthLayout hero={authAssets.login.hero} variant="login">
      <title>{pageTitle('Sign in')}</title>
      <div className="flex flex-col gap-9 short:gap-5">
        <AuthHeader title="Welcome Back" subtitle="Your memories are waiting. Sign in to continue." />
        <LoginForm />
        <AuthSwitchPrompt
          prompt="New to Moonlight Photo Studio?"
          linkLabel="Create an account"
          to={ROUTES.register}
        />
      </div>
    </AuthLayout>
  )
}

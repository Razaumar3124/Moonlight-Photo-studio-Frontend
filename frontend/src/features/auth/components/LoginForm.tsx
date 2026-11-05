import { UserRound } from 'lucide-react'
import { PasswordField } from '@/components/ui/PasswordField'
import { TextField } from '@/components/ui/TextField'
import { TextLink } from '@/components/ui/TextLink'
import { ROUTES } from '@/config/routes'
import { useLoginForm } from '../hooks/useLoginForm'
import { IDENTIFIER_MAX_LENGTH, PASSWORD_MAX_LENGTH } from '../lib/loginValidation'
import { AuthForm } from './AuthForm'

export function LoginForm() {
  const { field, handleSubmit, submitting, formError } = useLoginForm()

  return (
    <AuthForm
      label="Sign in"
      onSubmit={handleSubmit}
      formError={formError}
      submitting={submitting}
      submitLabel="Sign In"
      submittingLabel="Signing in…"
    >
      <TextField
        {...field('identifier')}
        label="Mobile No. or Email"
        placeholder="Enter your mobile no. or email"
        leftIcon={<UserRound />}
        type="text"
        required
        maxLength={IDENTIFIER_MAX_LENGTH}
        autoComplete="username"
        autoCapitalize="none"
        autoCorrect="off"
        spellCheck={false}
        enterKeyHint="next"
      />

      <div className="flex flex-col gap-2.5">
        <PasswordField
          {...field('password')}
          label="Password"
          placeholder="Enter your password"
          required
          maxLength={PASSWORD_MAX_LENGTH}
          autoComplete="current-password"
          enterKeyHint="go"
        />
        {/* Padding + negative margin: ≥ 36px tap target without changing the layout. */}
        <TextLink to={ROUTES.forgotPassword} className="-my-2 self-end py-2 text-sm">
          Forgot Password?
        </TextLink>
      </div>
    </AuthForm>
  )
}

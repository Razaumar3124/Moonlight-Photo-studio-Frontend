import { Mail, UserRound } from 'lucide-react'
import { PasswordField } from '@/components/ui/PasswordField'
import { PhoneField } from '@/components/ui/PhoneField'
import { TextField } from '@/components/ui/TextField'
import { useRegisterForm } from '../hooks/useRegisterForm'
import {
  EMAIL_MAX_LENGTH,
  FULL_NAME_MAX_LENGTH,
  PASSWORD_HINT,
  PASSWORD_MAX_LENGTH,
  PHONE_MAX_LENGTH,
} from '../lib/registerValidation'
import { AuthForm } from './AuthForm'

/**
 * Register form. Fields follow the mockup (Email, Mobile, Password) plus Full Name, which the
 * backend requires (API_ALIGNMENT M2). It comes first, the conventional position, and uses the
 * same field style.
 */
export function RegisterForm() {
  const { field, handleSubmit, submitting, formError } = useRegisterForm()

  return (
    <AuthForm
      label="Create account"
      onSubmit={handleSubmit}
      formError={formError}
      submitting={submitting}
      submitLabel="Create Account"
      submittingLabel="Creating account…"
      submitVariant="primary-gradient"
      compact
    >
      <TextField
        {...field('fullName')}
        label="Full Name"
        placeholder="Enter your full name"
        leftIcon={<UserRound />}
        type="text"
        required
        maxLength={FULL_NAME_MAX_LENGTH}
        autoComplete="name"
        autoCapitalize="words"
        // Names aren't dictionary words: no red squiggles under "Aarav".
        spellCheck={false}
        enterKeyHint="next"
      />

      <TextField
        {...field('email')}
        label="Email Address"
        placeholder="Enter your email address"
        leftIcon={<Mail />}
        type="email"
        inputMode="email"
        required
        maxLength={EMAIL_MAX_LENGTH}
        autoComplete="email"
        autoCapitalize="none"
        autoCorrect="off"
        spellCheck={false}
        enterKeyHint="next"
      />

      <PhoneField
        {...field('phone')}
        label="Mobile Number"
        placeholder="Enter your mobile number"
        required
        maxLength={PHONE_MAX_LENGTH}
        enterKeyHint="next"
      />

      <PasswordField
        {...field('password')}
        label="Password"
        placeholder="Create a password"
        hint={PASSWORD_HINT}
        required
        maxLength={PASSWORD_MAX_LENGTH}
        autoComplete="new-password"
        enterKeyHint="go"
      />
    </AuthForm>
  )
}

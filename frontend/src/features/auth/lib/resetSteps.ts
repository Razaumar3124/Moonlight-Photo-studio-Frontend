export type ResetStep = 'email' | 'code' | 'password'

/** Heading copy for each step (the page renders it above the flow). */
export const RESET_STEP_COPY: Record<ResetStep, { title: string; subtitle: string }> = {
  email: {
    title: 'Reset Password',
    subtitle: 'Enter your email and we’ll send you a verification code.',
  },
  code: { title: 'Check Your Email', subtitle: 'Enter the 6-digit code to continue.' },
  password: { title: 'New Password', subtitle: 'Choose a new password for your account.' },
}

import type { ReactNode } from 'react'
import { TextLink } from '@/components/ui/TextLink'
import type { AppRoute } from '@/config/routes'

interface AuthSwitchPromptProps {
  prompt: ReactNode
  linkLabel: ReactNode
  to: AppRoute
}

/** "New to Moonlight Photo Studio? Create an account" / "Already have an account? Sign in". */
export function AuthSwitchPrompt({ prompt, linkLabel, to }: AuthSwitchPromptProps) {
  return (
    <p className="text-center text-sm text-ink-700 sm:text-base auth-fluid:text-[length:var(--auth-prompt-size)] auth-fluid:leading-[1.4]">
      {prompt}{' '}
      <TextLink to={to} className="whitespace-nowrap">
        {linkLabel}
      </TextLink>
    </p>
  )
}

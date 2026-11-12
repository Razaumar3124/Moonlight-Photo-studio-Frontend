import { useLocation } from 'react-router-dom'
import { Alert } from '@/components/feedback/Alert'
import { useAuth } from '../authContext'

/** One-off message above the sign-in form: password just reset, or the session ended on its own. */
export function LoginNotice() {
  const { notice } = useAuth()
  const state = useLocation().state as { passwordReset?: boolean } | null

  if (state?.passwordReset) {
    return <Alert tone="success">Your password has been reset. Sign in with your new password.</Alert>
  }
  if (notice === 'expired') return <Alert tone="info">Your session has ended. Please sign in again.</Alert>
  if (notice === 'unreachable') {
    return <Alert tone="info">We couldn’t reach the server to restore your session. Please sign in.</Alert>
  }
  return null
}

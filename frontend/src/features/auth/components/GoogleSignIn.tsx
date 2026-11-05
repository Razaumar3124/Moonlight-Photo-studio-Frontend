import { useState } from 'react'
import { Alert } from '@/components/feedback/Alert'
import { GoogleButton } from './GoogleButton'

/**
 * "Continue with Google" + its placeholder notice, shared by Login and Register.
 * TODO(Phase 5): replace the notice with the Google Identity Services flow → POST /auth/google (M3).
 */
export function GoogleSignIn() {
  const [showNotice, setShowNotice] = useState(false)

  return (
    <div className="flex flex-col gap-3">
      <GoogleButton onClick={() => setShowNotice(true)} />
      {showNotice && (
        <Alert tone="info">
          Google sign-in is coming soon. Please use your mobile number or email for now.
        </Alert>
      )}
    </div>
  )
}

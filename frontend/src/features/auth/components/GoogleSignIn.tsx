import { useEffect, useRef, useState } from 'react'
import { Alert } from '@/components/feedback/Alert'
import { env } from '@/config/env'
import { useAuth } from '../authContext'
import { mapGoogleError } from '../lib/authErrors'
import {
  prepareGoogleSignIn,
  releaseGoogleSignIn,
  type GoogleAccountsId,
  type GoogleCredentialResponse,
} from '../lib/googleIdentity'
import { GoogleButton } from './GoogleButton'

type Availability = 'loading' | 'ready' | 'unavailable'

/** Google renders its button between 200 and 400px wide. */
const MIN_WIDTH = 200
const MAX_WIDTH = 400

/**
 * "Continue with Google", shared by Login and Register (one flow: the backend signs existing
 * users in and creates new ones).
 *
 * Google's own button is rendered (Identity Services only hands out an ID token through it) and
 * sized to the form column; it is replaced by the styled `GoogleButton`, disabled, while the
 * script loads or when Google sign-in can't be offered (no client ID configured, script blocked).
 * The ID token goes straight to POST /auth/google; it is never stored or logged.
 */
export function GoogleSignIn() {
  const { loginWithGoogle } = useAuth()
  const clientId = env.googleClientId
  const [availability, setAvailability] = useState<Availability>(clientId ? 'loading' : 'unavailable')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const hostRef = useRef<HTMLDivElement>(null)
  const gsiRef = useRef<GoogleAccountsId | null>(null)
  const busyRef = useRef(false)
  const abortRef = useRef<AbortController | null>(null)
  const signInRef = useRef(loginWithGoogle)
  useEffect(() => {
    signInRef.current = loginWithGoogle
  }, [loginWithGoogle])

  useEffect(() => {
    if (!clientId) return
    const lifecycle = new AbortController()

    const onCredential = async ({ credential }: GoogleCredentialResponse) => {
      if (busyRef.current) return
      if (!credential) {
        setError('Google didn’t return a sign-in. Please try again.')
        return
      }
      const controller = new AbortController()
      abortRef.current = controller
      busyRef.current = true
      setBusy(true)
      setError(null)
      try {
        await signInRef.current(credential, controller.signal)
      } catch (cause) {
        if (!controller.signal.aborted) setError(mapGoogleError(cause))
      } finally {
        busyRef.current = false
        if (!controller.signal.aborted) setBusy(false)
      }
    }

    prepareGoogleSignIn(clientId, onCredential)
      .then((gsi) => {
        if (lifecycle.signal.aborted) return
        gsiRef.current = gsi
        setAvailability('ready')
      })
      .catch(() => {
        if (!lifecycle.signal.aborted) setAvailability('unavailable')
      })

    return () => {
      lifecycle.abort()
      abortRef.current?.abort()
      releaseGoogleSignIn(onCredential)
    }
  }, [clientId])

  // Once the host element exists, let Google draw its button into it and keep it column-wide.
  useEffect(() => {
    const host = hostRef.current
    const gsi = gsiRef.current
    if (availability !== 'ready' || !host || !gsi) return
    const lastWidth = { current: 0 }
    const draw = () => {
      const width = Math.round(Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, host.clientWidth)))
      if (width === lastWidth.current) return
      lastWidth.current = width
      host.replaceChildren()
      gsi.renderButton(host, {
        type: 'standard',
        theme: 'outline',
        size: 'large',
        text: 'continue_with',
        shape: 'rectangular',
        logo_alignment: 'left',
        width,
        locale: 'en',
      })
    }
    draw()
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(draw)
    observer.observe(host)
    return () => observer.disconnect()
  }, [availability])

  return (
    <div className="flex flex-col gap-3">
      {availability === 'ready' ? (
        <div className="relative">
          {/* Always mounted while ready so Google can draw into it. */}
          <div
            ref={hostRef}
            className="flex min-h-12 items-center justify-center aria-busy:pointer-events-none aria-busy:opacity-50"
            aria-busy={busy}
          />
          {busy && (
            <p role="status" className="mt-2 text-center text-sm text-ink-700">
              Signing in with Google…
            </p>
          )}
        </div>
      ) : (
        <GoogleButton disabled aria-disabled="true" />
      )}

      {availability === 'unavailable' && (
        <Alert tone="info">
          Google sign-in isn’t available right now. Please use your email or mobile number.
        </Alert>
      )}
      {error && <Alert tone="error">{error}</Alert>}
    </div>
  )
}

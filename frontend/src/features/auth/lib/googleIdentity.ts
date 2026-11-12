/**
 * Google Identity Services (GIS) loader. The "Sign in with Google" button hands back an ID token
 * (a signed JWT); we forward it to POST /auth/google, where the backend verifies the signature,
 * issuer, audience and expiry. Nothing from Google is trusted client-side.
 */

export interface GoogleCredentialResponse {
  /** The ID token (JWT). Treat as a secret: never log or store it. */
  credential?: string
}

interface GoogleButtonConfig {
  type?: 'standard' | 'icon'
  theme?: 'outline' | 'filled_blue' | 'filled_black'
  size?: 'large' | 'medium' | 'small'
  text?: 'signin_with' | 'signup_with' | 'continue_with' | 'signin'
  shape?: 'rectangular' | 'pill'
  logo_alignment?: 'left' | 'center'
  /** Pixels, 200–400. */
  width?: number
}

interface GoogleAccountsId {
  initialize: (config: {
    client_id: string
    callback: (response: GoogleCredentialResponse) => void
    ux_mode?: 'popup' | 'redirect'
    auto_select?: boolean
    itp_support?: boolean
  }) => void
  renderButton: (parent: HTMLElement, config: GoogleButtonConfig) => void
}

declare global {
  interface Window {
    google?: { accounts?: { id?: GoogleAccountsId } }
  }
}

export const GOOGLE_SCRIPT_SRC = 'https://accounts.google.com/gsi/client'

let scriptPromise: Promise<GoogleAccountsId> | null = null
let initializedFor: string | null = null
let currentCallback: ((response: GoogleCredentialResponse) => void) | null = null

/** Loads the GIS script once. A failed load (offline, blocked) is not cached, so a retry can work. */
function loadScript(): Promise<GoogleAccountsId> {
  scriptPromise ??= new Promise<GoogleAccountsId>((resolve, reject) => {
    const fail = (message: string) => {
      scriptPromise = null
      reject(new Error(message))
    }
    const existing = window.google?.accounts?.id
    if (existing) return resolve(existing)

    const script = document.createElement('script')
    script.src = GOOGLE_SCRIPT_SRC
    script.async = true
    script.defer = true
    script.onload = () => {
      const gsi = window.google?.accounts?.id
      if (gsi) resolve(gsi)
      else fail('Google Identity Services did not initialise')
    }
    script.onerror = () => {
      script.remove()
      fail('Google Identity Services could not be loaded')
    }
    document.head.append(script)
  })
  return scriptPromise
}

/**
 * Load GIS and initialise it for `clientId`. GIS must be initialised once per page, so the
 * callback is held in a module variable that each mounted button replaces.
 */
export async function prepareGoogleSignIn(
  clientId: string,
  onCredential: (response: GoogleCredentialResponse) => void,
): Promise<GoogleAccountsId> {
  const gsi = await loadScript()
  currentCallback = onCredential
  if (initializedFor !== clientId) {
    gsi.initialize({
      client_id: clientId,
      callback: (response) => currentCallback?.(response),
      ux_mode: 'popup',
      auto_select: false,
      itp_support: true,
    })
    initializedFor = clientId
  }
  return gsi
}

/** Stop delivering credentials to an unmounted button. */
export function releaseGoogleSignIn(onCredential: (response: GoogleCredentialResponse) => void) {
  if (currentCallback === onCredential) currentCallback = null
}

export type { GoogleAccountsId, GoogleButtonConfig }

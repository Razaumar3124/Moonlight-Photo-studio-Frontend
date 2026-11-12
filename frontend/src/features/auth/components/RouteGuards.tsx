import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { PageLoader } from '@/components/layout/PageLoader'
import { ROUTES } from '@/config/routes'
import { useAuth } from '../authContext'
import { postLoginPath } from '../lib/redirect'

/** Signed-in pages. While the session is being restored nothing is decided; a visitor is sent to sign in. */
export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  const location = useLocation()

  if (status === 'loading') return <PageLoader />
  if (status === 'unauthenticated') {
    return <Navigate to={ROUTES.login} replace state={{ from: location.pathname + location.search }} />
  }
  return children
}

/** Sign-in / register / forgot-password: signed-in visitors go straight to the app (or where they were headed). */
export function GuestRoute({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  const location = useLocation()

  if (status === 'loading') return <PageLoader />
  if (status === 'authenticated') return <Navigate to={postLoginPath(location.state)} replace />
  return children
}

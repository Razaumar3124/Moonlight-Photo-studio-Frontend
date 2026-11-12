import { lazy, Suspense, type ReactNode } from 'react'
import { createBrowserRouter, Navigate } from 'react-router-dom'
import { PageLoader } from '@/components/layout/PageLoader'
import { ROUTES } from '@/config/routes'
import { GuestRoute, ProtectedRoute } from '@/features/auth/components/RouteGuards'
import { RouteErrorPage } from './RouteErrorPage'

// Each page is code-split so a visitor on /login never downloads the planner bundle.
const LoginPage = lazy(() => import('@/features/auth/pages/LoginPage'))
const RegisterPage = lazy(() => import('@/features/auth/pages/RegisterPage'))
const ForgotPasswordPage = lazy(() => import('@/features/auth/pages/ForgotPasswordPage'))
const MemoryWallPage = lazy(() => import('@/features/memory-wall/pages/MemoryWallPage'))
const NotFoundPage = lazy(() => import('@/app/NotFoundPage'))

const withSuspense = (node: ReactNode) => <Suspense fallback={<PageLoader />}>{node}</Suspense>

export const router = createBrowserRouter([
  {
    // Pathless layout route: one error boundary for every page (render errors, failed chunk loads).
    errorElement: <RouteErrorPage />,
    children: [
      // Signed-in visitors land in the planner; ProtectedRoute sends everyone else to sign in.
      { path: ROUTES.home, element: <Navigate to={ROUTES.memoryWall} replace /> },
      { path: ROUTES.login, element: <GuestRoute>{withSuspense(<LoginPage />)}</GuestRoute> },
      { path: ROUTES.register, element: <GuestRoute>{withSuspense(<RegisterPage />)}</GuestRoute> },
      {
        path: ROUTES.forgotPassword,
        element: <GuestRoute>{withSuspense(<ForgotPasswordPage />)}</GuestRoute>,
      },
      {
        path: ROUTES.memoryWall,
        element: <ProtectedRoute>{withSuspense(<MemoryWallPage />)}</ProtectedRoute>,
      },
      { path: '*', element: withSuspense(<NotFoundPage />) },
    ],
  },
])

import { lazy, Suspense, type ReactNode } from 'react'
import { createBrowserRouter, Navigate } from 'react-router-dom'
import { PageLoader } from '@/components/layout/PageLoader'
import { ROUTES } from '@/config/routes'
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
      { path: ROUTES.home, element: <Navigate to={ROUTES.login} replace /> },
      { path: ROUTES.login, element: withSuspense(<LoginPage />) },
      { path: ROUTES.register, element: withSuspense(<RegisterPage />) },
      { path: ROUTES.forgotPassword, element: withSuspense(<ForgotPasswordPage />) },
      // TODO(Phase 5): wrap in a <ProtectedRoute> once the FastAPI auth endpoints are live.
      { path: ROUTES.memoryWall, element: withSuspense(<MemoryWallPage />) },
      { path: '*', element: withSuspense(<NotFoundPage />) },
    ],
  },
])

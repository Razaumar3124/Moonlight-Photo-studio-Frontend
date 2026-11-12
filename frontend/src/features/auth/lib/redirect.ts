import { ROUTES } from '@/config/routes'

const AUTH_PATHS: readonly string[] = [ROUTES.login, ROUTES.register, ROUTES.forgotPassword]

/**
 * Where to go after signing in: the page the visitor was sent away from (`state.from`, set by
 * ProtectedRoute), else the planner. Only same-app absolute paths are honoured, so a crafted
 * navigation state can never become an open redirect, and never back to an auth page.
 */
export function postLoginPath(state: unknown): string {
  const from = (state as { from?: unknown } | null)?.from
  if (typeof from !== 'string' || !/^\/(?![/\\])/.test(from)) return ROUTES.memoryWall
  const pathname = from.split(/[?#]/)[0] ?? ''
  if (AUTH_PATHS.includes(pathname) || pathname === ROUTES.home) return ROUTES.memoryWall
  return from
}

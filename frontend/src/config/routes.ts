/** Single source of truth for URL paths. Never hard-code a path string in a component. */
export const ROUTES = {
  home: '/',
  login: '/login',
  register: '/register',
  forgotPassword: '/forgot-password',
  memoryWall: '/memory-wall',
  /** Public report link prefix: `/q/<token>` (see features/quotes). */
  sharedReport: '/q',
} as const

export type AppRoute = (typeof ROUTES)[keyof typeof ROUTES]

/** Single source of truth for URL paths. Never hard-code a path string in a component. */
export const ROUTES = {
  home: '/',
  login: '/login',
  register: '/register',
  forgotPassword: '/forgot-password',
  memoryWall: '/memory-wall',
} as const

export type AppRoute = (typeof ROUTES)[keyof typeof ROUTES]

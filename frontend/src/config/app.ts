export const APP_NAME = 'Moonlight Photo Studio'

/** Document title for a page: "Sign in · Moonlight Photo Studio". Every page sets one. */
export function pageTitle(page?: string): string {
  return page ? `${page} · ${APP_NAME}` : APP_NAME
}

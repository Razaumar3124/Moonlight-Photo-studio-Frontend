/** Typed access to Vite env vars. Only VITE_-prefixed vars reach the browser. */
export const env = {
  /** Base URL for the FastAPI backend, including the version prefix. Defaults to the dev proxy. */
  apiBaseUrl: (import.meta.env.VITE_API_BASE_URL ?? '/api/v1').replace(/\/+$/, ''),
  googleClientId: import.meta.env.VITE_GOOGLE_CLIENT_ID ?? '',
  isDev: import.meta.env.DEV,
} as const

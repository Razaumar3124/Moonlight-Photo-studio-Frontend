import { isRouteErrorResponse, useRouteError } from 'react-router-dom'
import { PlaceholderPage } from '@/components/layout/PlaceholderPage'
import { Button } from '@/components/ui/Button'
import { TextLink } from '@/components/ui/TextLink'
import { ROUTES } from '@/config/routes'

/** A lazy route chunk that no longer exists (typically after a new deploy) or a dropped connection. */
function isChunkLoadError(error: unknown): boolean {
  return (
    error instanceof Error &&
    /dynamically imported module|Importing a module script failed|error loading dynamically|Failed to fetch/i.test(
      error.message,
    )
  )
}

/**
 * Router-level error boundary. Shows a friendly message instead of React Router's developer
 * screen. Error details are never rendered in production (they can reveal internals); in dev
 * they're logged to the console.
 */
export function RouteErrorPage() {
  const error = useRouteError()
  if (import.meta.env.DEV) console.error(error)

  if (isRouteErrorResponse(error) && error.status === 404) {
    return (
      <PlaceholderPage title="Page not found" subtitle="This frame is empty.">
        <TextLink to={ROUTES.login}>Back to sign in</TextLink>
      </PlaceholderPage>
    )
  }

  const chunkError = isChunkLoadError(error)

  return (
    <PlaceholderPage
      title={chunkError ? 'Update available' : 'Something went wrong'}
      subtitle={
        chunkError
          ? 'A newer version of the site is available, or the connection dropped. Reload to continue.'
          : 'An unexpected error occurred. Reloading the page usually fixes it.'
      }
    >
      <div className="flex flex-col items-center gap-4">
        <Button onClick={() => window.location.reload()}>Reload page</Button>
        <TextLink to={ROUTES.login}>Back to sign in</TextLink>
      </div>
    </PlaceholderPage>
  )
}

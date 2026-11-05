/**
 * Full-screen fallback while a lazy-loaded page chunk downloads. It fades in after 150ms, so
 * fast (cached) loads don't flash a spinner.
 */
export function PageLoader() {
  return (
    <div
      className="grid min-h-dvh animate-fade-in-delayed place-items-center bg-cream-100"
      role="status"
      aria-live="polite"
    >
      <span
        aria-hidden
        className="size-8 animate-spin rounded-full border-2 border-cream-300 border-t-brand-600"
      />
      <span className="sr-only">Loading…</span>
    </div>
  )
}

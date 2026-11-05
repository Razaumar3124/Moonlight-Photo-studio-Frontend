import type { ReactNode } from 'react'
import { EstablishedTag } from '@/components/brand/EstablishedTag'
import { pageTitle } from '@/config/app'

interface PlaceholderPageProps {
  title: string
  subtitle?: string
  children?: ReactNode
}

/**
 * Simple centred page for routes whose real UI hasn't been built yet, and for 404/error states.
 * Always sets the document title.
 */
export function PlaceholderPage({ title, subtitle, children }: PlaceholderPageProps) {
  return (
    <main className="mx-auto flex min-h-dvh max-w-xl flex-col items-center justify-center gap-4 px-4 text-center break-words sm:px-6">
      <title>{pageTitle(title)}</title>
      <EstablishedTag />
      <h1 className="text-4xl sm:text-5xl">{title}</h1>
      {subtitle && <p className="text-ink-500">{subtitle}</p>}
      {children}
    </main>
  )
}

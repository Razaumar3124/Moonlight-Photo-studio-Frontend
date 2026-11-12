// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import SharedReportRedirect from './SharedReportRedirect'

const TOKEN = 'LDcWktm_9DuGs9LEC5SGRMBedXLRnZgGj2tq5Zumqp8'
const replace = vi.fn<(url: string) => void>()

beforeEach(() => {
  replace.mockReset()
  Object.defineProperty(window, 'location', {
    configurable: true,
    value: { ...window.location, replace, origin: 'http://localhost:5173' },
  })
})
afterEach(cleanup)

function renderAt(path: string) {
  const router = createMemoryRouter([{ path: '/q/:token', element: <SharedReportRedirect /> }], {
    initialEntries: [path],
  })
  render(<RouterProvider router={router} />)
}

describe('SharedReportRedirect', () => {
  it('sends a well-formed token to the API-rendered report', async () => {
    renderAt(`/q/${TOKEN}`)
    await screen.findByRole('status')
    expect(replace).toHaveBeenCalledWith(`/api/v1/quotes/share/${TOKEN}`)
  })

  it.each(['short', 'has.dots.in.it.1234567890', `${'a'.repeat(200)}`, '..%2F..%2Fetc%2Fpasswd0000'])(
    'does not redirect a malformed token (%s) and shows the not-found page',
    async (token) => {
      renderAt(`/q/${token}`)
      expect(await screen.findByRole('heading')).toBeTruthy()
      expect(replace).not.toHaveBeenCalled()
    },
  )
})

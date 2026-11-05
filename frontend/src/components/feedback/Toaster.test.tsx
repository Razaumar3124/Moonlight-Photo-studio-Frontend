// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useToast, type ToastInput } from './toastContext'
import { ToastProvider } from './Toaster'

beforeEach(() => {
  vi.useFakeTimers()
})
afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

function Trigger({ input }: { input: ToastInput }) {
  const toast = useToast()
  return (
    <button type="button" onClick={() => toast(input)}>
      show
    </button>
  )
}

function showToast(input: ToastInput) {
  render(
    <ToastProvider>
      <Trigger input={input} />
    </ToastProvider>,
  )
  fireEvent.click(screen.getByText('show'))
}

const toastFor = (text: string) => screen.getByText(text).parentElement as HTMLElement

describe('Toaster', () => {
  it('auto-dismisses plain toasts after 5 s', () => {
    showToast({ message: 'Saved' })
    act(() => vi.advanceTimersByTime(4900))
    expect(screen.queryByText('Saved')).not.toBeNull()
    act(() => vi.advanceTimersByTime(200))
    expect(screen.queryByText('Saved')).toBeNull()
  })

  it('gives actionable toasts longer and pauses while hovered or focused', () => {
    const onUndo = vi.fn<() => void>()
    showToast({ message: 'Reset', action: { label: 'Undo', onClick: onUndo } })
    act(() => vi.advanceTimersByTime(6000))
    const undo = screen.getByRole('button', { name: 'Undo' })

    fireEvent.mouseEnter(toastFor('Reset'))
    act(() => vi.advanceTimersByTime(60_000))
    expect(screen.queryByText('Reset')).not.toBeNull()
    fireEvent.mouseLeave(toastFor('Reset'))

    fireEvent.focus(undo)
    act(() => vi.advanceTimersByTime(60_000))
    expect(screen.queryByText('Reset')).not.toBeNull()

    fireEvent.click(undo)
    expect(onUndo).toHaveBeenCalledOnce()
    expect(screen.queryByText('Reset')).toBeNull()
  })

  it('resumes with the remaining time after the pointer leaves', () => {
    showToast({ message: 'Hello', action: { label: 'Undo', onClick: () => {} } })
    act(() => vi.advanceTimersByTime(7000))
    fireEvent.mouseEnter(toastFor('Hello'))
    act(() => vi.advanceTimersByTime(30_000))
    fireEvent.mouseLeave(toastFor('Hello'))
    act(() => vi.advanceTimersByTime(900))
    expect(screen.queryByText('Hello')).not.toBeNull()
    act(() => vi.advanceTimersByTime(200))
    expect(screen.queryByText('Hello')).toBeNull()
  })
})

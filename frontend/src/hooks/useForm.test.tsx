// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useForm, type UseFormOptions } from './useForm'

afterEach(cleanup)

type F = 'a' | 'b'

function Harness(props: Partial<UseFormOptions<F>>) {
  const form = useForm<F>({
    fields: ['a', 'b'],
    initialValues: { a: '', b: '' },
    validateField: (_f, v) => (v.trim() ? undefined : 'Required'),
    onSubmit: async () => {},
    mapSubmitError: () => ({ formError: 'Failed' }),
    ...props,
  })
  const a = form.field('a')
  const b = form.field('b')
  return (
    <form onSubmit={form.handleSubmit} noValidate>
      {form.formError && <p role="alert">{form.formError}</p>}
      <label htmlFor="a">A</label>
      <input id="a" {...a} aria-invalid={!!a.error} />
      {a.error && <span>a: {a.error}</span>}
      <label htmlFor="b">B</label>
      <input id="b" {...b} aria-invalid={!!b.error} />
      {b.error && <span>b: {b.error}</span>}
      <button type="submit">{form.submitting ? 'Busy' : 'Go'}</button>
    </form>
  )
}

describe('useForm', () => {
  it('shows all errors on submit and focuses the first invalid field', async () => {
    render(<Harness />)
    await userEvent.click(screen.getByRole('button', { name: 'Go' }))
    expect(screen.getByText('a: Required')).toBeTruthy()
    expect(screen.getByText('b: Required')).toBeTruthy()
    expect(document.activeElement).toBe(screen.getByLabelText('A'))
  })

  it('does not flag an empty field on blur, but validates a filled one', async () => {
    render(<Harness validateField={(_f, v) => (v.length >= 3 ? undefined : 'Too short')} />)
    const a = screen.getByLabelText('A')
    fireEvent.blur(a)
    expect(screen.queryByText(/a: /)).toBeNull()
    await userEvent.type(a, 'xy')
    fireEvent.blur(a)
    expect(screen.getByText('a: Too short')).toBeTruthy()
    await userEvent.type(a, 'z') // live re-validation once touched
    expect(screen.queryByText('a: Too short')).toBeNull()
  })

  it('keeps both values when two fields change in the same tick (browser autofill)', async () => {
    const onSubmit = vi.fn<UseFormOptions<F>['onSubmit']>(async () => {})
    render(<Harness onSubmit={onSubmit} />)
    act(() => {
      fireEvent.change(screen.getByLabelText('A'), { target: { value: 'user@example.com' } })
      fireEvent.change(screen.getByLabelText('B'), { target: { value: 'secret' } })
    })
    await userEvent.click(screen.getByRole('button', { name: 'Go' }))
    expect(onSubmit).toHaveBeenCalledWith({ a: 'user@example.com', b: 'secret' }, expect.any(AbortSignal))
  })

  it('runs only one submission at a time (double click / double Enter)', async () => {
    let resolve: () => void = () => {}
    const onSubmit = vi.fn<UseFormOptions<F>['onSubmit']>(() => new Promise<void>((r) => (resolve = r)))
    render(<Harness initialValues={{ a: 'x', b: 'y' }} onSubmit={onSubmit} />)
    const form = screen.getByRole('button', { name: 'Go' }).closest('form')
    if (!form) throw new Error('form missing')
    act(() => {
      fireEvent.submit(form)
      fireEvent.submit(form)
      fireEvent.submit(form)
    })
    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('button', { name: 'Busy' })).toBeTruthy()
    await act(async () => resolve())
    expect(screen.getByRole('button', { name: 'Go' })).toBeTruthy()
  })

  it('maps a thrown error to field errors and focuses that field', async () => {
    render(
      <Harness
        initialValues={{ a: 'x', b: 'y' }}
        onSubmit={async () => {
          throw new Error('nope')
        }}
        mapSubmitError={() => ({ fieldErrors: { b: 'Taken' } })}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Go' }))
    expect(await screen.findByText('b: Taken')).toBeTruthy()
    expect(document.activeElement).toBe(screen.getByLabelText('B'))
  })

  it('shows a form-level error and clears it when the user edits', async () => {
    render(
      <Harness
        initialValues={{ a: 'x', b: 'y' }}
        onSubmit={async () => {
          throw new Error('nope')
        }}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Go' }))
    expect(await screen.findByRole('alert')).toBeTruthy()
    await userEvent.type(screen.getByLabelText('A'), '!')
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('aborts an in-flight submission on unmount and ignores its result', async () => {
    let signal: AbortSignal | undefined
    const mapSubmitError = vi.fn<UseFormOptions<F>['mapSubmitError']>(() => ({ formError: 'x' }))
    const { unmount } = render(
      <Harness
        initialValues={{ a: 'x', b: 'y' }}
        onSubmit={(_v, s) => {
          signal = s
          return new Promise((_r, reject) =>
            s.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError'))),
          )
        }}
        mapSubmitError={mapSubmitError}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Go' }))
    unmount()
    await Promise.resolve()
    expect(signal?.aborted).toBe(true)
    expect(mapSubmitError).not.toHaveBeenCalled()
  })
})

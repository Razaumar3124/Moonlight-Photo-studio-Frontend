import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from 'react'

export type FormValues<F extends string> = Record<F, string>
export type FieldErrors<F extends string> = Partial<Record<F, string>>

export interface SubmitErrorResult<F extends string> {
  fieldErrors?: FieldErrors<F>
  formError?: string
}

export interface UseFormOptions<F extends string> {
  /** All fields, in visual order (used to focus the first invalid one). */
  fields: readonly F[]
  initialValues: FormValues<F>
  /** Return an error message, or undefined when valid. `values` allows cross-field rules. */
  validateField: (field: F, value: string, values: FormValues<F>) => string | undefined
  /** Do the work (API call, navigation). Throw to report failure; honour `signal` for aborts. */
  onSubmit: (values: FormValues<F>, signal: AbortSignal) => Promise<void>
  /** Turn a thrown error into field errors and/or a form-level message. */
  mapSubmitError: (error: unknown) => SubmitErrorResult<F>
}

/**
 * Small, dependency-free form state for the auth forms (and any simple text form).
 *
 * Behaviour:
 * - errors show on blur (if the field has content) or on submit; after that they update live;
 * - on a failed submit, focus moves to the first invalid field;
 * - one submission at a time (ref guard, so double-clicks/Enter in the same tick can't race);
 * - an in-flight submission is aborted on unmount;
 * - values are tracked in a ref too, so batched events (browser autofill of several fields in one
 *   tick) never overwrite each other with stale state.
 */
export function useForm<F extends string>({
  fields,
  initialValues,
  validateField,
  onSubmit,
  mapSubmitError,
}: UseFormOptions<F>) {
  const [values, setValues] = useState<FormValues<F>>(initialValues)
  const [errors, setErrors] = useState<FieldErrors<F>>({})
  const [formError, setFormError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const valuesRef = useRef(values)
  const touchedRef = useRef<Partial<Record<F, boolean>>>({})
  const submittingRef = useRef(false)
  const abortRef = useRef<AbortController | null>(null)
  const inputRefs = useRef<Partial<Record<F, HTMLInputElement | null>>>({})
  const refCallbacks = useRef<Partial<Record<F, (el: HTMLInputElement | null) => void>>>({})

  useEffect(() => () => abortRef.current?.abort(), [])

  const setFieldError = (field: F, message: string | undefined) =>
    setErrors((prev) => (prev[field] === message ? prev : { ...prev, [field]: message }))

  const focusField = (field: F) => inputRefs.current[field]?.focus()

  const validateAll = (current: FormValues<F>): FieldErrors<F> => {
    const result: FieldErrors<F> = {}
    for (const field of fields) {
      const message = validateField(field, current[field], current)
      if (message) result[field] = message
    }
    return result
  }

  const handleChange = (field: F) => (event: ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value
    const next = { ...valuesRef.current, [field]: value }
    valuesRef.current = next
    setValues(next)
    setFormError(null)
    if (touchedRef.current[field]) setFieldError(field, validateField(field, value, next))
  }

  const handleBlur = (field: F) => () => {
    const value = valuesRef.current[field]
    // Don't scold an empty field the user merely tabbed through.
    if (!value) return
    touchedRef.current[field] = true
    setFieldError(field, validateField(field, value, valuesRef.current))
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (submittingRef.current) return

    const current = valuesRef.current
    const nextErrors = validateAll(current)
    setErrors(nextErrors)
    for (const field of fields) touchedRef.current[field] = true
    const firstInvalid = fields.find((f) => nextErrors[f])
    if (firstInvalid) {
      focusField(firstInvalid)
      return
    }

    const controller = new AbortController()
    abortRef.current = controller
    submittingRef.current = true
    setSubmitting(true)
    setFormError(null)

    try {
      await onSubmit(current, controller.signal)
    } catch (error) {
      if (controller.signal.aborted) return
      const result = mapSubmitError(error)
      const fieldErrors: FieldErrors<F> = result.fieldErrors ?? {}
      setErrors(fieldErrors)
      setFormError(result.formError ?? null)
      const firstServerInvalid = fields.find((f) => fieldErrors[f])
      if (firstServerInvalid) focusField(firstServerInvalid)
    } finally {
      submittingRef.current = false
      if (!controller.signal.aborted) setSubmitting(false)
    }
  }

  const getRef = (field: F) =>
    (refCallbacks.current[field] ??= (el: HTMLInputElement | null) => {
      inputRefs.current[field] = el
    })

  /** Props to spread onto a TextField/PasswordField: value, handlers, error and ref. */
  const field = (name: F) => ({
    name,
    value: values[name],
    onChange: handleChange(name),
    onBlur: handleBlur(name),
    error: errors[name],
    ref: getRef(name),
  })

  return { field, handleSubmit, submitting, formError, values, errors }
}

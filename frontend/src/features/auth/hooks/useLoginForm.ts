import { useForm } from '@/hooks/useForm'
import { useAuth } from '../authContext'
import {
  LOGIN_FIELDS,
  LOGIN_INITIAL_VALUES,
  mapLoginError,
  toLoginRequest,
  validateLoginField,
} from '../lib/loginValidation'

/**
 * Login form: generic form behaviour from `useForm` + login rules, payload and error mapping.
 * On success the AuthProvider flips to `authenticated` and GuestRoute navigates onward.
 */
export function useLoginForm() {
  const { login } = useAuth()

  return useForm({
    fields: LOGIN_FIELDS,
    initialValues: LOGIN_INITIAL_VALUES,
    validateField: (field, value) => validateLoginField(field, value),
    mapSubmitError: mapLoginError,
    onSubmit: async (values, signal) => {
      await login(toLoginRequest(values), signal)
    },
  })
}

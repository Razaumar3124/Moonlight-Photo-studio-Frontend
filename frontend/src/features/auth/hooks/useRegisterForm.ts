import { useForm } from '@/hooks/useForm'
import { useAuth } from '../authContext'
import {
  mapRegisterError,
  REGISTER_FIELDS,
  REGISTER_INITIAL_VALUES,
  toRegisterRequest,
  validateRegisterField,
} from '../lib/registerValidation'

/**
 * Register form: generic form behaviour from `useForm` + register rules, payload and errors.
 * Registering signs the user in (the API returns a session), so GuestRoute navigates onward.
 */
export function useRegisterForm() {
  const { register } = useAuth()

  return useForm({
    fields: REGISTER_FIELDS,
    initialValues: REGISTER_INITIAL_VALUES,
    validateField: (field, value) => validateRegisterField(field, value),
    mapSubmitError: mapRegisterError,
    onSubmit: async (values, signal) => {
      await register(toRegisterRequest(values), signal)
    },
  })
}

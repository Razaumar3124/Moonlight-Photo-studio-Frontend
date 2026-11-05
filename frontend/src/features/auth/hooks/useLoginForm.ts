import { useNavigate } from 'react-router-dom'
import { ROUTES } from '@/config/routes'
import { useForm } from '@/hooks/useForm'
import {
  LOGIN_FIELDS,
  LOGIN_INITIAL_VALUES,
  mapLoginError,
  toLoginRequest,
  validateLoginField,
} from '../lib/loginValidation'
import { mockLogin } from '../lib/mockAuth'

/** Login form: generic form behaviour from `useForm` + login rules, payload and error mapping. */
export function useLoginForm() {
  const navigate = useNavigate()

  return useForm({
    fields: LOGIN_FIELDS,
    initialValues: LOGIN_INITIAL_VALUES,
    validateField: (field, value) => validateLoginField(field, value),
    mapSubmitError: mapLoginError,
    onSubmit: async (values, signal) => {
      // TODO(Phase 5): swap mockLogin for services/auth.login (same signature) + store tokens.
      await mockLogin(toLoginRequest(values), signal)
      navigate(ROUTES.memoryWall, { replace: true })
    },
  })
}

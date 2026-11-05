import { useNavigate } from 'react-router-dom'
import { ROUTES } from '@/config/routes'
import { useForm } from '@/hooks/useForm'
import { mockRegister } from '../lib/mockAuth'
import {
  mapRegisterError,
  REGISTER_FIELDS,
  REGISTER_INITIAL_VALUES,
  toRegisterRequest,
  validateRegisterField,
} from '../lib/registerValidation'

/** Register form: generic form behaviour from `useForm` + register rules, payload and errors. */
export function useRegisterForm() {
  const navigate = useNavigate()

  return useForm({
    fields: REGISTER_FIELDS,
    initialValues: REGISTER_INITIAL_VALUES,
    validateField: (field, value) => validateRegisterField(field, value),
    mapSubmitError: mapRegisterError,
    onSubmit: async (values, signal) => {
      // TODO(Phase 5): swap mockRegister for services/auth.register (same signature) + store tokens.
      await mockRegister(toRegisterRequest(values), signal)
      navigate(ROUTES.memoryWall, { replace: true })
    },
  })
}

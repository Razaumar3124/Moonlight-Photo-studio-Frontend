import { RouterProvider } from 'react-router-dom'
import { ToastProvider } from '@/components/feedback/Toaster'
import { AuthProvider } from '@/features/auth/AuthProvider'
import { router } from './router'

export default function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </ToastProvider>
  )
}

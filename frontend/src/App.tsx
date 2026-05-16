import { RouterProvider } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { SystemProvider } from './system/SystemContext'
import { router } from './router'

export default function App() {
  return (
    <SystemProvider>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </SystemProvider>
  )
}

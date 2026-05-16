import { Navigate, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import type { ReactNode } from 'react'
import { useAuth } from './AuthContext'
import { useSystem } from '../system/SystemContext'

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { status, loading: systemLoading, error: systemError } = useSystem()
  const { user, loading: authLoading } = useAuth()
  const location = useLocation()
  const { t } = useTranslation()

  if (systemLoading) {
    return (
      <div className="flex h-screen items-center justify-center text-text-muted">
        {t('protectedRoute.checking')}
      </div>
    )
  }

  if (systemError || !status) {
    return (
      <div className="flex h-screen items-center justify-center text-rose-400">
        {t('system.unavailable', { message: systemError ?? '' })}
      </div>
    )
  }

  if (status.mode === 'practice') {
    return <>{children}</>
  }

  if (!status.initialized) {
    return <Navigate to="/setup" replace />
  }

  if (authLoading) {
    return (
      <div className="flex h-screen items-center justify-center text-text-muted">
        {t('protectedRoute.checking')}
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />
  }

  return <>{children}</>
}

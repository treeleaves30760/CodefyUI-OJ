import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { setupAdmin } from '../api/system'
import { useAuth } from '../auth/AuthContext'
import { useSystem } from '../system/SystemContext'
import { LanguageSwitcher } from '../components/LanguageSwitcher'

export function Setup() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const { status, refresh } = useSystem()
  const { login } = useAuth()

  const [email, setEmail] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (status?.mode === 'practice') return <Navigate to="/" replace />
  if (status && status.initialized) return <Navigate to="/login" replace />

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await setupAdmin({ email, password, display_name: displayName })
      // Auto-login so the new admin lands in an authenticated session.
      await login({ email, password })
      await refresh()
      navigate('/', { replace: true })
    } catch (err) {
      setError(extractError(err, t('common.unknownError')))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <div className="flex justify-end px-6 pt-4">
        <LanguageSwitcher />
      </div>
      <main className="mx-auto mt-12 max-w-md px-6">
        <h1 className="text-3xl font-bold tracking-tight">{t('setup.title')}</h1>
        <p className="mt-2 text-text-muted">{t('setup.subtitle')}</p>
        <div className="mt-3 rounded border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
          {t('setup.warning')}
        </div>

        <form onSubmit={handleSubmit} className="mt-8 space-y-4">
          <Field label={t('setup.displayName')}>
            <input
              type="text"
              required
              autoFocus
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="input"
            />
          </Field>
          <Field label={t('setup.email')}>
            <input
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="input"
            />
          </Field>
          <Field label={t('setup.passwordWithHint')}>
            <input
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input"
            />
          </Field>

          {error && <div className="text-sm text-red-400">{error}</div>}

          <button type="submit" disabled={submitting} className="btn-primary w-full">
            {submitting ? t('setup.submitting') : t('setup.submit')}
          </button>
        </form>
      </main>
    </>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-sm text-text-muted">{label}</span>
      <div className="mt-1">{children}</div>
    </label>
  )
}

function extractError(err: unknown, fallback: string): string {
  if (typeof err === 'object' && err !== null && 'response' in err) {
    const resp = (err as { response?: { data?: { detail?: unknown } } }).response
    const detail = resp?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map((d) => (d as { msg?: string }).msg ?? '').join(', ')
  }
  if (err instanceof Error) return err.message
  return fallback
}

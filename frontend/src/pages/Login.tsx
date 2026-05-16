import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../auth/AuthContext'
import { LanguageSwitcher } from '../components/LanguageSwitcher'

interface LocationState {
  from?: { pathname: string }
}

export function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const { t } = useTranslation()
  const from = (location.state as LocationState | null)?.from?.pathname ?? '/'

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await login({ email, password })
      navigate(from, { replace: true })
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
        <h1 className="text-3xl font-bold tracking-tight">{t('auth.login.title')}</h1>
        <p className="mt-2 text-text-muted">{t('auth.login.subtitle')}</p>

        <form onSubmit={handleSubmit} className="mt-8 space-y-4">
          <Field label={t('auth.login.email')}>
            <input
              type="email"
              required
              autoFocus
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="input"
            />
          </Field>
          <Field label={t('auth.login.password')}>
            <input
              type="password"
              required
              minLength={8}
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input"
            />
          </Field>

          {error && <div className="text-sm text-red-400">{error}</div>}

          <button type="submit" disabled={submitting} className="btn-primary w-full">
            {submitting ? t('auth.login.submitting') : t('auth.login.submit')}
          </button>
        </form>

        <p className="mt-6 text-sm text-text-muted">
          {t('auth.login.noAccount')}{' '}
          <Link to="/register" className="text-accent hover:underline">
            {t('auth.login.register')}
          </Link>
        </p>
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

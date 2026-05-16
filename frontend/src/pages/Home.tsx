import { useEffect, useState } from 'react'
import { Trans, useTranslation } from 'react-i18next'
import { useAuth } from '../auth/AuthContext'
import { useSystem } from '../system/SystemContext'
import { apiClient } from '../api/client'

interface HealthResponse {
  status: string
  app: string
}

export function Home() {
  const { user } = useAuth()
  const { status } = useSystem()
  const { t } = useTranslation()
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    apiClient
      .get<HealthResponse>('/health')
      .then((res) => setHealth(res.data))
      .catch((err) => setError(err.message ?? 'unknown error'))
  }, [])

  const isPractice = status?.mode === 'practice'
  const greetingName = isPractice ? t('home.practiceUser') : user?.display_name || user?.email || ''

  return (
    <div>
      <h1 className="text-4xl font-bold tracking-tight">
        <Trans
          i18nKey="home.welcome"
          values={{ name: greetingName }}
          components={{ accent: <span className="text-accent" /> }}
        />
      </h1>
      <p className="mt-3 text-text-muted">
        {isPractice ? t('home.practiceTagline') : t('home.tagline')}
      </p>

      <section className="mt-10 rounded-lg border border-border bg-surface p-6">
        <h2 className="text-lg font-semibold">{t('home.backendCheck')}</h2>
        {health ? (
          <div className="mt-3 text-sm">
            <span className="rounded bg-accent/20 px-2 py-1 font-mono text-accent">
              {health.status}
            </span>{' '}
            <span className="text-text-muted">— {health.app}</span>
          </div>
        ) : error ? (
          <div className="mt-3 text-sm text-red-400">
            {t('home.backendOffline', { message: error })}
          </div>
        ) : (
          <div className="mt-3 text-sm text-text-muted">{t('home.checking')}</div>
        )}
      </section>

      <section className="mt-8 grid gap-4 sm:grid-cols-3">
        {isPractice ? (
          <Stat
            label={t('home.availableProblems')}
            value={status?.practice_problem_count != null ? String(status.practice_problem_count) : '—'}
          />
        ) : (
          <>
            <Stat label={t('home.activeContests')} value="—" />
            <Stat label={t('home.availableProblems')} value="—" />
            <Stat label={t('home.bestRank')} value="—" />
          </>
        )}
      </section>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="text-xs text-text-muted">{label}</div>
      <div className="mt-1 text-2xl font-semibold tracking-tight">{value}</div>
    </div>
  )
}

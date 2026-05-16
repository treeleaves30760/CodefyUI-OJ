import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  listContests,
  type ContestListItem,
  type ContestRuntimeStatus,
} from '../api/contests'

const STATUS_STYLE: Record<ContestRuntimeStatus, string> = {
  active: 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10',
  upcoming: 'text-sky-400 border-sky-500/30 bg-sky-500/10',
  past: 'text-text-muted border-border bg-surface',
}

export function ContestList() {
  const { t } = useTranslation()
  const [contests, setContests] = useState<ContestListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<ContestRuntimeStatus | 'all'>('all')

  useEffect(() => {
    setLoading(true)
    listContests(filter === 'all' ? undefined : filter)
      .then(setContests)
      .catch((e) => setError(e.message ?? t('common.loadFailed')))
      .finally(() => setLoading(false))
  }, [filter, t])

  return (
    <div>
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">{t('contests.list.title')}</h1>
          <p className="mt-2 text-text-muted">{t('contests.list.subtitle')}</p>
        </div>
        <div className="flex gap-1 text-xs">
          {(['all', 'active', 'upcoming', 'past'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`rounded border px-3 py-1.5 transition-colors ${
                filter === f
                  ? 'border-accent bg-accent/10 text-accent'
                  : 'border-border text-text-muted hover:border-accent/50'
              }`}
            >
              {f === 'all' ? t('contests.filterAll') : t(`contests.status.${f}` as const)}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-8 grid gap-4">
        {loading ? (
          <div className="rounded-lg border border-border bg-surface p-6 text-text-muted">
            {t('common.loading')}
          </div>
        ) : error ? (
          <div className="rounded-lg border border-border bg-surface p-6 text-rose-400">
            {error}
          </div>
        ) : contests.length === 0 ? (
          <div className="rounded-lg border border-border bg-surface p-6 text-text-muted">
            {t('contests.list.empty')}
          </div>
        ) : (
          contests.map((c) => (
            <Link
              key={c.id}
              to={`/contests/${c.slug}`}
              className="block rounded-lg border border-border bg-surface p-5 transition-colors hover:border-accent/50"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-3">
                    <h2 className="text-lg font-semibold">{c.title}</h2>
                    <span
                      className={`rounded border px-2 py-0.5 text-xs ${STATUS_STYLE[c.runtime_status]}`}
                    >
                      {t(`contests.status.${c.runtime_status}` as const)}
                    </span>
                  </div>
                  <div className="mt-1 font-mono text-xs text-text-muted">{c.slug}</div>
                </div>
                <div className="text-right text-xs text-text-muted">
                  <div>{t('contests.list.problemCount', { count: c.problem_count })}</div>
                </div>
              </div>
              <div className="mt-3 grid gap-1 text-xs text-text-muted sm:grid-cols-2">
                <div>
                  {t('contests.list.startAt', { at: new Date(c.start_at).toLocaleString() })}
                </div>
                <div>
                  {t('contests.list.endAt', { at: new Date(c.end_at).toLocaleString() })}
                </div>
              </div>
            </Link>
          ))
        )}
      </div>
    </div>
  )
}

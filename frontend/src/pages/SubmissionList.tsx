import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { listSubmissions, type SubmissionListItem, type SubmissionStatus } from '../api/submissions'

const STATUS_STYLE: Record<SubmissionStatus, string> = {
  queued: 'text-amber-400 border-amber-500/30 bg-amber-500/10',
  judging: 'text-sky-400 border-sky-500/30 bg-sky-500/10',
  judged: 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10',
  invalid: 'text-rose-400 border-rose-500/30 bg-rose-500/10',
  runtime_error: 'text-rose-400 border-rose-500/30 bg-rose-500/10',
  timeout: 'text-rose-400 border-rose-500/30 bg-rose-500/10',
  error: 'text-rose-400 border-rose-500/30 bg-rose-500/10',
}

export function SubmissionList() {
  const { t } = useTranslation()
  const [submissions, setSubmissions] = useState<SubmissionListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listSubmissions()
      .then(setSubmissions)
      .catch((e) => setError(e.message ?? t('common.loadFailed')))
      .finally(() => setLoading(false))
  }, [t])

  return (
    <div>
      <h1 className="text-3xl font-bold tracking-tight">{t('submissions.list.title')}</h1>

      <div className="mt-8 overflow-hidden rounded-lg border border-border bg-surface">
        {loading ? (
          <div className="p-6 text-text-muted">{t('common.loading')}</div>
        ) : error ? (
          <div className="p-6 text-rose-400">{error}</div>
        ) : submissions.length === 0 ? (
          <div className="p-6 text-text-muted">{t('submissions.list.empty')}</div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-text-muted">
              <tr>
                <th className="px-4 py-3 font-medium">{t('submissions.list.colId')}</th>
                <th className="px-4 py-3 font-medium">{t('submissions.list.colProblem')}</th>
                <th className="px-4 py-3 font-medium">{t('submissions.list.colStatus')}</th>
                <th className="px-4 py-3 font-medium">{t('submissions.list.colScore')}</th>
                <th className="px-4 py-3 font-medium">{t('submissions.list.colRuntime')}</th>
                <th className="px-4 py-3 font-medium">{t('submissions.list.colSubmittedAt')}</th>
              </tr>
            </thead>
            <tbody>
              {submissions.map((s) => (
                <tr key={s.id} className="border-b border-border last:border-0 hover:bg-bg/50">
                  <td className="px-4 py-3 font-mono text-xs text-text-muted">{s.id}</td>
                  <td className="px-4 py-3">
                    <Link to={`/submissions/${s.id}`} className="text-text hover:text-accent">
                      {t('submissions.list.problemLink', { id: s.problem_id })}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`rounded border px-2 py-0.5 text-xs ${STATUS_STYLE[s.status]}`}>
                      {t(`submissions.status.${s.status}` as const)}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono">
                    {s.score !== null ? s.score.toFixed(1) : '—'}
                  </td>
                  <td className="px-4 py-3 text-text-muted">
                    {s.runtime_ms !== null ? `${s.runtime_ms} ms` : '—'}
                  </td>
                  <td className="px-4 py-3 text-text-muted">
                    {new Date(s.submitted_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

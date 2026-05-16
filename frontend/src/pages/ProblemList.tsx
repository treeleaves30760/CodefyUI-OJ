import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { listProblems, type ProblemDifficulty, type ProblemListItem } from '../api/problems'

const DIFFICULTY_STYLE: Record<ProblemDifficulty, string> = {
  easy: 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10',
  medium: 'text-amber-400 border-amber-500/30 bg-amber-500/10',
  hard: 'text-rose-400 border-rose-500/30 bg-rose-500/10',
}

export function ProblemList() {
  const { t } = useTranslation()
  const [problems, setProblems] = useState<ProblemListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    listProblems(true)
      .then(setProblems)
      .catch((e) => setError(e.message ?? t('common.loadFailed')))
      .finally(() => setLoading(false))
  }, [t])

  return (
    <div>
      <h1 className="text-3xl font-bold tracking-tight">{t('problems.list.title')}</h1>
      <p className="mt-2 text-text-muted">{t('problems.list.subtitle')}</p>

      <div className="mt-8 overflow-hidden rounded-lg border border-border bg-surface">
        {loading ? (
          <div className="p-6 text-text-muted">{t('common.loading')}</div>
        ) : error ? (
          <div className="p-6 text-rose-400">{error}</div>
        ) : problems.length === 0 ? (
          <div className="p-6 text-text-muted">{t('problems.list.empty')}</div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-text-muted">
              <tr>
                <th className="px-6 py-3 font-medium">{t('problems.list.colTitle')}</th>
                <th className="px-4 py-3 font-medium">{t('problems.list.colDifficulty')}</th>
                <th className="px-4 py-3 font-medium">{t('problems.list.colTags')}</th>
                <th className="px-4 py-3 font-medium">{t('problems.list.colTestData')}</th>
              </tr>
            </thead>
            <tbody>
              {problems.map((p) => (
                <tr
                  key={p.id}
                  className="border-b border-border last:border-0 hover:bg-bg/50"
                >
                  <td className="px-6 py-4">
                    <Link
                      to={`/problems/${p.slug}`}
                      className="font-medium text-text hover:text-accent"
                    >
                      {p.title}
                    </Link>
                    <div className="mt-0.5 font-mono text-xs text-text-muted">{p.slug}</div>
                  </td>
                  <td className="px-4 py-4">
                    <span
                      className={`rounded border px-2 py-0.5 text-xs ${DIFFICULTY_STYLE[p.difficulty]}`}
                    >
                      {t(`problems.difficulty.${p.difficulty}` as const)}
                    </span>
                  </td>
                  <td className="px-4 py-4 text-text-muted">
                    {p.tags.length > 0 ? p.tags.join(', ') : '—'}
                  </td>
                  <td className="px-4 py-4 text-text-muted">
                    {p.has_test_data ? (
                      <span className="text-accent">✓</span>
                    ) : (
                      <span className="text-rose-400">{t('problems.list.testDataMissing')}</span>
                    )}
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

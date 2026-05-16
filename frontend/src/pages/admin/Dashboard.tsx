import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  getAdminStats,
  listAdminSubmissions,
  type AdminStats,
  type AdminSubmissionRow,
} from '../../api/admin'

export function AdminDashboard() {
  const { t } = useTranslation()
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [subs, setSubs] = useState<AdminSubmissionRow[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [s, ss] = await Promise.all([
          getAdminStats(),
          listAdminSubmissions(10),
        ])
        if (cancelled) return
        setStats(s)
        setSubs(ss)
      } catch (err) {
        if (cancelled) return
        const msg = err instanceof Error ? err.message : t('common.unknownError')
        setError(msg)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [t])

  if (loading) return <div className="text-text-muted">{t('common.loading')}</div>
  if (error) return <div className="text-rose-400">{error}</div>
  if (!stats) return null

  return (
    <div>
      <h1 className="text-3xl font-bold tracking-tight">{t('admin.dashboard.title')}</h1>
      <p className="mt-2 text-text-muted">{t('admin.dashboard.subtitle')}</p>

      <section className="mt-8 grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label={t('admin.dashboard.statUsersTotal')} value={stats.users_total} />
        <StatCard label={t('admin.dashboard.statProblems')} value={stats.problems_total} sub={t('admin.dashboard.statProblemsSub', { published: stats.problems_published })} />
        <StatCard label={t('admin.dashboard.statContests')} value={stats.contests_total} sub={t('admin.dashboard.statContestsSub', { active: stats.contests_active })} />
        <StatCard label={t('admin.dashboard.statSubmissions')} value={stats.submissions_total} sub={t('admin.dashboard.statSubmissionsSub', { count: stats.submissions_last_24h })} />
      </section>

      <section className="mt-8">
        <h2 className="text-lg font-semibold">{t('admin.dashboard.roleBreakdown')}</h2>
        <div className="mt-3 flex gap-3 text-sm">
          <RoleBadge color="text-emerald-300" label={t('admin.role.admin')} count={stats.users_by_role.admin ?? 0} />
          <RoleBadge color="text-sky-300" label={t('admin.role.teacher')} count={stats.users_by_role.teacher ?? 0} />
          <RoleBadge color="text-text" label={t('admin.role.student')} count={stats.users_by_role.student ?? 0} />
        </div>
      </section>

      <section className="mt-10">
        <div className="flex items-baseline justify-between">
          <h2 className="text-lg font-semibold">{t('admin.dashboard.recentSubmissions')}</h2>
          <span className="text-xs text-text-muted">{t('admin.dashboard.recentNotice')}</span>
        </div>
        <div className="mt-3 overflow-hidden rounded-lg border border-border bg-surface">
          {subs.length === 0 ? (
            <div className="p-6 text-text-muted">{t('admin.dashboard.noSubmissions')}</div>
          ) : (
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border text-text-muted">
                <tr>
                  <th className="px-4 py-3 font-medium">#</th>
                  <th className="px-4 py-3 font-medium">{t('admin.dashboard.colUser')}</th>
                  <th className="px-4 py-3 font-medium">{t('admin.dashboard.colProblem')}</th>
                  <th className="px-4 py-3 font-medium">{t('admin.dashboard.colStatus')}</th>
                  <th className="px-4 py-3 font-medium">{t('admin.dashboard.colScore')}</th>
                  <th className="px-4 py-3 font-medium">{t('admin.dashboard.colTime')}</th>
                </tr>
              </thead>
              <tbody>
                {subs.map((s) => (
                  <tr key={s.id} className="border-b border-border last:border-0">
                    <td className="px-4 py-3 font-mono text-xs text-text-muted">{s.id}</td>
                    <td className="px-4 py-3">{s.user_email}</td>
                    <td className="px-4 py-3">
                      <Link to={`/problems/${s.problem_slug}`} className="text-accent hover:underline">
                        {s.problem_slug}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-text-muted">{s.status}</td>
                    <td className="px-4 py-3">{s.score ?? '—'}</td>
                    <td className="px-4 py-3 text-text-muted">
                      {new Date(s.submitted_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>
    </div>
  )
}

function StatCard({ label, value, sub }: { label: string; value: number; sub?: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-5">
      <div className="text-xs uppercase tracking-wide text-text-muted">{label}</div>
      <div className="mt-2 text-3xl font-semibold tabular-nums">{value}</div>
      {sub && <div className="mt-1 text-xs text-text-muted">{sub}</div>}
    </div>
  )
}

function RoleBadge({ color, label, count }: { color: string; label: string; count: number }) {
  return (
    <div className={`rounded border border-border bg-surface px-3 py-2 ${color}`}>
      <span className="text-xs uppercase tracking-wide text-text-muted">{label}</span>
      <span className="ml-2 font-semibold tabular-nums">{count}</span>
    </div>
  )
}

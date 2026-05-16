import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  listAdminUsers,
  updateAdminUser,
  type AdminUser,
} from '../../api/admin'
import type { UserRole } from '../../api/auth'
import { extractApiError } from '../../api/error'
import { useAuth } from '../../auth/AuthContext'

export function AdminUsers() {
  const { t } = useTranslation()
  const { user: me } = useAuth()
  const [users, setUsers] = useState<AdminUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [rowErrors, setRowErrors] = useState<Record<number, string>>({})

  async function refresh() {
    try {
      setError(null)
      const data = await listAdminUsers()
      setUsers(data)
    } catch (err) {
      setError(extractApiError(err, t('common.unknownError')))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function changeRole(u: AdminUser, role: UserRole) {
    setRowErrors((p) => ({ ...p, [u.id]: '' }))
    try {
      const updated = await updateAdminUser(u.id, { role })
      setUsers((prev) => prev.map((x) => (x.id === u.id ? updated : x)))
    } catch (err) {
      setRowErrors((p) => ({ ...p, [u.id]: extractApiError(err, t('common.unknownError')) }))
    }
  }

  async function toggleActive(u: AdminUser) {
    setRowErrors((p) => ({ ...p, [u.id]: '' }))
    try {
      const updated = await updateAdminUser(u.id, { is_active: !u.is_active })
      setUsers((prev) => prev.map((x) => (x.id === u.id ? updated : x)))
    } catch (err) {
      setRowErrors((p) => ({ ...p, [u.id]: extractApiError(err, t('common.unknownError')) }))
    }
  }

  return (
    <div>
      <h1 className="text-3xl font-bold tracking-tight">{t('admin.users.title')}</h1>
      <p className="mt-1 text-text-muted">{t('admin.users.subtitle')}</p>

      {error && (
        <div className="mt-4 rounded border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-300">
          {error}
        </div>
      )}

      <section className="mt-8 overflow-hidden rounded-lg border border-border bg-surface">
        {loading ? (
          <div className="p-6 text-text-muted">{t('common.loading')}</div>
        ) : users.length === 0 ? (
          <div className="p-6 text-text-muted">{t('admin.users.empty')}</div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-text-muted">
              <tr>
                <th className="px-4 py-3 font-medium">#</th>
                <th className="px-4 py-3 font-medium">{t('admin.users.colEmail')}</th>
                <th className="px-4 py-3 font-medium">{t('admin.users.colDisplayName')}</th>
                <th className="px-4 py-3 font-medium">{t('admin.users.colRole')}</th>
                <th className="px-4 py-3 font-medium">{t('admin.users.colActive')}</th>
                <th className="px-4 py-3 font-medium">{t('admin.users.colCreated')}</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const isSelf = me?.id === u.id
                return (
                  <tr key={u.id} className="border-b border-border last:border-0 align-top">
                    <td className="px-4 py-3 font-mono text-xs text-text-muted">{u.id}</td>
                    <td className="px-4 py-3">
                      {u.email}
                      {isSelf && <span className="ml-2 rounded bg-accent/15 px-1.5 py-0.5 text-xs text-accent">you</span>}
                    </td>
                    <td className="px-4 py-3 text-text-muted">{u.display_name || '—'}</td>
                    <td className="px-4 py-3">
                      <select
                        value={u.role}
                        onChange={(e) => void changeRole(u, e.target.value as UserRole)}
                        className="input w-32"
                      >
                        <option value="student">student</option>
                        <option value="teacher">teacher</option>
                        <option value="admin">admin</option>
                      </select>
                      {u.is_superuser && (
                        <span className="ml-2 rounded bg-amber-500/15 px-1.5 py-0.5 text-xs text-amber-300">
                          superuser
                        </span>
                      )}
                      {rowErrors[u.id] && (
                        <div className="mt-1 text-xs text-rose-400">{rowErrors[u.id]}</div>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => void toggleActive(u)}
                        className={`rounded border px-2 py-1 text-xs ${
                          u.is_active
                            ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
                            : 'border-rose-500/40 bg-rose-500/10 text-rose-300'
                        }`}
                      >
                        {u.is_active ? t('admin.users.active') : t('admin.users.inactive')}
                      </button>
                    </td>
                    <td className="px-4 py-3 text-xs text-text-muted">
                      {new Date(u.created_at).toLocaleString()}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}

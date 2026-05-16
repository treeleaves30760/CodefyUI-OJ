import { NavLink, Outlet, Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../auth/AuthContext'
import { LanguageSwitcher } from '../../components/LanguageSwitcher'

export function AdminLayout() {
  const { t } = useTranslation()
  const { user, logout } = useAuth()

  const navItems = [
    { to: '/admin', label: t('admin.nav.dashboard'), end: true },
    { to: '/admin/problems', label: t('admin.nav.problems') },
    { to: '/admin/contests', label: t('admin.nav.contests') },
    { to: '/admin/users', label: t('admin.nav.users') },
  ]

  return (
    <div className="flex min-h-screen">
      <aside className="w-60 shrink-0 border-r border-border bg-surface px-4 py-6">
        <Link to="/admin" className="block px-2 text-lg font-semibold tracking-tight">
          CodefyUI <span className="text-accent">OJ</span>
          <div className="text-xs font-normal text-text-muted">{t('admin.consoleBadge')}</div>
        </Link>

        <nav className="mt-8 space-y-1 text-sm">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `block rounded px-3 py-2 transition-colors ${
                  isActive
                    ? 'bg-accent/15 text-accent'
                    : 'text-text-muted hover:bg-bg/50 hover:text-text'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="mt-10 border-t border-border pt-4 text-xs text-text-muted">
          <div className="px-2">
            <div className="truncate">{user?.display_name || user?.email}</div>
            <div className="mt-0.5">
              <span className="rounded bg-accent/15 px-1.5 py-0.5 text-accent">
                {user?.role}
              </span>
            </div>
          </div>
          <div className="mt-4 space-y-1">
            <Link
              to="/"
              className="block rounded px-2 py-1.5 hover:bg-bg/50 hover:text-text"
            >
              ← {t('admin.backToApp')}
            </Link>
            <button
              onClick={() => void logout()}
              className="w-full rounded px-2 py-1.5 text-left hover:bg-bg/50 hover:text-text"
            >
              {t('navbar.logout')}
            </button>
          </div>
          <div className="mt-3 px-2">
            <LanguageSwitcher />
          </div>
        </div>
      </aside>

      <main className="flex-1 px-8 py-8">
        <Outlet />
      </main>
    </div>
  )
}

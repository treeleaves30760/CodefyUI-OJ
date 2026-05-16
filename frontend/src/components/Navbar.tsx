import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../auth/AuthContext'
import { useSystem } from '../system/SystemContext'
import { LanguageSwitcher } from './LanguageSwitcher'

export function Navbar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const { t } = useTranslation()
  const { status } = useSystem()
  const isPractice = status?.mode === 'practice'

  async function handleLogout() {
    await logout()
    navigate('/login')
  }

  return (
    <nav className="border-b border-border bg-surface">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
        <Link to="/" className="font-semibold tracking-tight">
          CodefyUI <span className="text-accent">OJ</span>
          {isPractice && (
            <span className="ml-2 rounded bg-sky-500/15 px-1.5 py-0.5 text-xs text-sky-300">
              {t('navbar.practiceBadge')}
            </span>
          )}
        </Link>
        <div className="flex items-center gap-4 text-sm">
          {isPractice ? (
            <>
              <Link to="/problems" className="text-text-muted hover:text-text">
                {t('navbar.problems')}
              </Link>
              <Link to="/submissions" className="text-text-muted hover:text-text">
                {t('navbar.submissions')}
              </Link>
            </>
          ) : user ? (
            <>
              <Link to="/contests" className="text-text-muted hover:text-text">
                {t('navbar.contests')}
              </Link>
              <Link to="/problems" className="text-text-muted hover:text-text">
                {t('navbar.problems')}
              </Link>
              <Link to="/submissions" className="text-text-muted hover:text-text">
                {t('navbar.submissions')}
              </Link>
              {(user.role === 'admin' || user.is_superuser) && (
                <Link
                  to="/admin"
                  className="rounded border border-accent/40 px-2 py-1 text-xs text-accent hover:bg-accent/10"
                >
                  {t('navbar.admin')}
                </Link>
              )}
              <span className="text-text-muted">
                {user.display_name || user.email}
                <span className="ml-2 rounded bg-accent/15 px-1.5 py-0.5 text-xs text-accent">
                  {user.role}
                </span>
              </span>
              <button
                onClick={handleLogout}
                className="rounded border border-border px-3 py-1 text-text-muted hover:border-accent hover:text-accent"
              >
                {t('navbar.logout')}
              </button>
            </>
          ) : (
            <>
              <Link to="/problems" className="text-text-muted hover:text-text">
                {t('navbar.problems')}
              </Link>
              <Link to="/login" className="text-text-muted hover:text-text">
                {t('navbar.login')}
              </Link>
              <Link
                to="/register"
                className="rounded bg-accent px-3 py-1 text-bg hover:bg-accent-hover"
              >
                {t('navbar.register')}
              </Link>
            </>
          )}
          <LanguageSwitcher />
        </div>
      </div>
    </nav>
  )
}

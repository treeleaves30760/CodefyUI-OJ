import { Link, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../auth/AuthContext'
import { LanguageSwitcher } from './LanguageSwitcher'

export function Navbar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const { t } = useTranslation()

  async function handleLogout() {
    await logout()
    navigate('/login')
  }

  return (
    <nav className="border-b border-border bg-surface">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
        <Link to="/" className="font-semibold tracking-tight">
          CodefyUI <span className="text-accent">OJ</span>
        </Link>
        <div className="flex items-center gap-4 text-sm">
          {user ? (
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

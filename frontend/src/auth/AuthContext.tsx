import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import {
  fetchMe,
  login as apiLogin,
  logout as apiLogout,
  register as apiRegister,
  type LoginPayload,
  type RegisterPayload,
  type User,
} from '../api/auth'
import { useSystem } from '../system/SystemContext'

const TOKEN_KEY = 'access_token'

interface AuthState {
  user: User | null
  loading: boolean
  login: (payload: LoginPayload) => Promise<void>
  register: (payload: RegisterPayload) => Promise<void>
  logout: () => Promise<void>
  refresh: () => Promise<void>
}

const AuthContext = createContext<AuthState | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const { status, loading: systemLoading } = useSystem()
  const isPractice = status?.mode === 'practice'

  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = useCallback(async () => {
    if (isPractice) {
      setUser(null)
      setLoading(false)
      return
    }
    const token = localStorage.getItem(TOKEN_KEY)
    if (!token) {
      setUser(null)
      setLoading(false)
      return
    }
    try {
      const me = await fetchMe()
      setUser(me)
    } catch {
      localStorage.removeItem(TOKEN_KEY)
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [isPractice])

  useEffect(() => {
    if (systemLoading) return
    void refresh()
  }, [refresh, systemLoading])

  const login = useCallback(async (payload: LoginPayload) => {
    const { access_token } = await apiLogin(payload)
    localStorage.setItem(TOKEN_KEY, access_token)
    const me = await fetchMe()
    setUser(me)
  }, [])

  const register = useCallback(
    async (payload: RegisterPayload) => {
      await apiRegister(payload)
      await login({ email: payload.email, password: payload.password })
    },
    [login],
  )

  const logout = useCallback(async () => {
    await apiLogout()
    localStorage.removeItem(TOKEN_KEY)
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within <AuthProvider>')
  return ctx
}

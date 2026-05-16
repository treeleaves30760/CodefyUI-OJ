import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { getSystemStatus, type SystemStatus } from '../api/system'

interface SystemContextValue {
  status: SystemStatus | null
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
}

const SystemContext = createContext<SystemContextValue | undefined>(undefined)

export function SystemProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const next = await getSystemStatus()
      setStatus(next)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'system status unavailable')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  return (
    <SystemContext.Provider value={{ status, loading, error, refresh }}>
      {children}
    </SystemContext.Provider>
  )
}

export function useSystem(): SystemContextValue {
  const ctx = useContext(SystemContext)
  if (!ctx) throw new Error('useSystem must be used within <SystemProvider>')
  return ctx
}

export function useIsPracticeMode(): boolean {
  const { status } = useSystem()
  return status?.mode === 'practice'
}

export function useIsInitialized(): boolean {
  const { status } = useSystem()
  if (!status) return false
  return status.initialized
}

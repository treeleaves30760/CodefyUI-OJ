export function extractApiError(err: unknown, fallback: string): string {
  if (typeof err === 'object' && err !== null && 'response' in err) {
    const resp = (err as { response?: { data?: { detail?: unknown } } }).response
    const detail = resp?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail
        .map((d) => {
          if (typeof d === 'string') return d
          if (typeof d === 'object' && d !== null && 'msg' in d) {
            return (d as { msg?: string }).msg ?? ''
          }
          return ''
        })
        .filter(Boolean)
        .join(', ')
    }
  }
  if (err instanceof Error) return err.message
  return fallback
}

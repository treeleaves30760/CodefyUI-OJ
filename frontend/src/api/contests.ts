import { apiClient } from './client'

export type ContestVisibility = 'public' | 'private' | 'invite_only'
export type ContestRuntimeStatus = 'upcoming' | 'active' | 'past'

export interface ContestProblemEntry {
  problem_slug: string
  points: number
  display_order: number
}

export interface ContestProblem {
  problem_id: number
  problem_slug: string
  problem_title: string
  points: number
  display_order: number
}

export interface ContestListItem {
  id: number
  slug: string
  title: string
  start_at: string
  end_at: string
  visibility: ContestVisibility
  runtime_status: ContestRuntimeStatus
  problem_count: number
}

export interface Contest {
  id: number
  slug: string
  title: string
  description_md: string
  start_at: string
  end_at: string
  visibility: ContestVisibility
  runtime_status: ContestRuntimeStatus
  created_by_user_id: number
  created_at: string
  updated_at: string
  problems: ContestProblem[]
  participant_count: number
  joined: boolean
}

export interface LeaderboardEntry {
  rank: number
  user_id: number
  display_name: string
  total_score: number
  per_problem: Record<string, number>
}

export interface Leaderboard {
  contest_id: number
  contest_slug: string
  generated_at: string
  entries: LeaderboardEntry[]
}

export interface ContestCreatePayload {
  slug: string
  title: string
  description_md?: string
  start_at: string
  end_at: string
  visibility: ContestVisibility
  problems?: ContestProblemEntry[]
}

export interface ContestUpdatePayload {
  title?: string
  description_md?: string
  start_at?: string
  end_at?: string
  visibility?: ContestVisibility
}

export async function listContests(status?: ContestRuntimeStatus): Promise<ContestListItem[]> {
  const { data } = await apiClient.get<ContestListItem[]>('/contests', {
    params: status ? { status } : {},
  })
  return data
}

export async function getContest(slug: string): Promise<Contest> {
  const { data } = await apiClient.get<Contest>(`/contests/${slug}`)
  return data
}

export async function joinContest(slug: string): Promise<Contest> {
  const { data } = await apiClient.post<Contest>(`/contests/${slug}/join`)
  return data
}

export async function createContest(body: ContestCreatePayload): Promise<Contest> {
  const { data } = await apiClient.post<Contest>('/contests', body)
  return data
}

export async function updateContest(slug: string, body: ContestUpdatePayload): Promise<Contest> {
  const { data } = await apiClient.put<Contest>(`/contests/${slug}`, body)
  return data
}

export async function deleteContest(slug: string): Promise<void> {
  await apiClient.delete(`/contests/${slug}`)
}

export async function addContestProblem(slug: string, entry: ContestProblemEntry): Promise<Contest> {
  const { data } = await apiClient.post<Contest>(`/contests/${slug}/problems`, entry)
  return data
}

export async function removeContestProblem(slug: string, problemSlug: string): Promise<void> {
  await apiClient.delete(`/contests/${slug}/problems/${problemSlug}`)
}

export async function getLeaderboard(slug: string): Promise<Leaderboard> {
  const { data } = await apiClient.get<Leaderboard>(`/contests/${slug}/leaderboard`)
  return data
}

/**
 * Open an SSE connection that pushes a fresh leaderboard on every contest
 * submission update. Returns the live EventSource so the caller can close
 * it on unmount. EventSource doesn't accept custom headers, so the bearer
 * token rides on the query string.
 */
export function streamLeaderboard(
  slug: string,
  handlers: {
    onSnapshot: (lb: Leaderboard) => void
    onOpen?: () => void
    onError?: (err: Event) => void
  },
): EventSource {
  const token = localStorage.getItem('access_token') ?? ''
  const qs = new URLSearchParams({ token }).toString()
  const url = `/api/contests/${slug}/leaderboard/stream?${qs}`
  const source = new EventSource(url)
  source.addEventListener('open', () => handlers.onOpen?.())
  source.addEventListener('leaderboard', (event) => {
    try {
      const parsed = JSON.parse((event as MessageEvent).data) as Leaderboard
      handlers.onSnapshot(parsed)
    } catch {
      // Drop malformed payloads silently — keepalive comments and partial
      // packets sometimes squeak through.
    }
  })
  source.addEventListener('error', (event) => handlers.onError?.(event))
  return source
}

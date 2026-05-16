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

export async function getLeaderboard(slug: string): Promise<Leaderboard> {
  const { data } = await apiClient.get<Leaderboard>(`/contests/${slug}/leaderboard`)
  return data
}

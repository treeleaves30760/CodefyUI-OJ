import { apiClient } from './client'

export type ProblemDifficulty = 'easy' | 'medium' | 'hard'

export interface ProblemListItem {
  id: number
  slug: string
  title: string
  difficulty: ProblemDifficulty
  tags: string[]
  published: boolean
  has_test_data: boolean
  created_at: string
}

export interface Problem extends ProblemListItem {
  statement_md: string
  starter_template_json: Record<string, unknown>
  judge_spec: Record<string, unknown>
  time_limit_seconds: number
  memory_limit_mb: number
  created_by_user_id: number
  updated_at: string
}

export async function listProblems(publishedOnly = true): Promise<ProblemListItem[]> {
  const { data } = await apiClient.get<ProblemListItem[]>('/problems', {
    params: { published_only: publishedOnly },
  })
  return data
}

export async function getProblem(slug: string): Promise<Problem> {
  const { data } = await apiClient.get<Problem>(`/problems/${slug}`)
  return data
}

export async function downloadTemplate(slug: string): Promise<Record<string, unknown>> {
  const { data } = await apiClient.get<Record<string, unknown>>(`/problems/${slug}/template`)
  return data
}

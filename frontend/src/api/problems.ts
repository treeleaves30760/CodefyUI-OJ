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

export interface ProblemWritePayload {
  slug: string
  title: string
  statement_md?: string
  difficulty?: ProblemDifficulty
  tags?: string[]
  starter_template_json: Record<string, unknown>
  judge_spec: Record<string, unknown>
  time_limit_seconds?: number
  memory_limit_mb?: number
  published?: boolean
  practice_visible?: boolean
}

export interface ProblemUpdatePayload {
  title?: string
  statement_md?: string
  difficulty?: ProblemDifficulty
  tags?: string[]
  starter_template_json?: Record<string, unknown>
  judge_spec?: Record<string, unknown>
  time_limit_seconds?: number
  memory_limit_mb?: number
  published?: boolean
  practice_visible?: boolean
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

export async function createProblem(body: ProblemWritePayload): Promise<Problem> {
  const { data } = await apiClient.post<Problem>('/problems', body)
  return data
}

export async function updateProblem(slug: string, body: ProblemUpdatePayload): Promise<Problem> {
  const { data } = await apiClient.put<Problem>(`/problems/${slug}`, body)
  return data
}

export async function deleteProblem(slug: string): Promise<void> {
  await apiClient.delete(`/problems/${slug}`)
}

export async function uploadTestData(slug: string, file: File): Promise<void> {
  const form = new FormData()
  form.append('file', file)
  await apiClient.post(`/problems/${slug}/test-data`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

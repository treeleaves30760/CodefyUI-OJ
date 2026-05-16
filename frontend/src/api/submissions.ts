import { apiClient } from './client'

export type SubmissionStatus =
  | 'queued'
  | 'judging'
  | 'judged'
  | 'invalid'
  | 'runtime_error'
  | 'timeout'
  | 'error'

export interface SubmissionListItem {
  id: number
  problem_id: number
  contest_id: number | null
  submitted_at: string
  status: SubmissionStatus
  score: number | null
  runtime_ms: number | null
}

export interface SubmissionDetail extends SubmissionListItem {
  user_id: number
  judge_started_at: string | null
  judge_finished_at: string | null
  judge_log: string
  raw_result: Record<string, unknown> | null
}

export interface SubmissionCreatePayload {
  problem_slug: string
  graph_json: Record<string, unknown>
  contest_id?: number | null
}

export async function createSubmission(
  payload: SubmissionCreatePayload,
): Promise<SubmissionDetail> {
  const { data } = await apiClient.post<SubmissionDetail>('/submissions', payload)
  return data
}

export async function listSubmissions(params?: {
  problem_slug?: string
  contest_id?: number
}): Promise<SubmissionListItem[]> {
  const { data } = await apiClient.get<SubmissionListItem[]>('/submissions', {
    params,
  })
  return data
}

export async function getSubmission(id: number): Promise<SubmissionDetail> {
  const { data } = await apiClient.get<SubmissionDetail>(`/submissions/${id}`)
  return data
}

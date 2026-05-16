import { apiClient } from './client'

export type AppMode = 'competition' | 'practice'

export interface SystemStatus {
  mode: AppMode
  initialized: boolean
  practice_problem_count: number
}

export interface AdminSetupPayload {
  email: string
  password: string
  display_name: string
}

export async function getSystemStatus(): Promise<SystemStatus> {
  const res = await apiClient.get<SystemStatus>('/system/status')
  return res.data
}

export async function setupAdmin(payload: AdminSetupPayload): Promise<void> {
  await apiClient.post('/system/setup', payload)
}

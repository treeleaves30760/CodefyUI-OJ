import { apiClient } from './client'
import type { UserRole } from './auth'

export interface AdminStats {
  users_total: number
  users_by_role: Record<UserRole, number>
  problems_total: number
  problems_published: number
  contests_total: number
  contests_active: number
  submissions_total: number
  submissions_last_24h: number
}

export interface AdminUser {
  id: number
  email: string
  display_name: string
  role: UserRole
  is_active: boolean
  is_superuser: boolean
  created_at: string
}

export interface AdminUserUpdate {
  role?: UserRole
  is_active?: boolean
}

export interface AdminSubmissionRow {
  id: number
  user_id: number
  user_email: string
  problem_id: number
  problem_slug: string
  contest_id: number | null
  status: string
  score: number | null
  submitted_at: string
}

export async function getAdminStats(): Promise<AdminStats> {
  const { data } = await apiClient.get<AdminStats>('/admin/stats')
  return data
}

export async function listAdminUsers(): Promise<AdminUser[]> {
  const { data } = await apiClient.get<AdminUser[]>('/admin/users')
  return data
}

export async function updateAdminUser(id: number, body: AdminUserUpdate): Promise<AdminUser> {
  const { data } = await apiClient.patch<AdminUser>(`/admin/users/${id}`, body)
  return data
}

export async function listAdminSubmissions(limit = 50): Promise<AdminSubmissionRow[]> {
  const { data } = await apiClient.get<AdminSubmissionRow[]>('/admin/submissions', {
    params: { limit },
  })
  return data
}

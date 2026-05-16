import { apiClient } from './client'

export type UserRole = 'student' | 'teacher' | 'admin'

export interface User {
  id: number
  email: string
  display_name: string
  role: UserRole
  is_active: boolean
  is_superuser: boolean
  is_verified: boolean
}

export interface RegisterPayload {
  email: string
  password: string
  display_name: string
}

export interface LoginPayload {
  email: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

export async function register(payload: RegisterPayload): Promise<User> {
  const { data } = await apiClient.post<User>('/auth/register', payload)
  return data
}

export async function login(payload: LoginPayload): Promise<TokenResponse> {
  const form = new URLSearchParams()
  form.append('username', payload.email)
  form.append('password', payload.password)
  const { data } = await apiClient.post<TokenResponse>('/auth/jwt/login', form, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })
  return data
}

export async function logout(): Promise<void> {
  await apiClient.post('/auth/jwt/logout').catch(() => undefined)
}

export async function fetchMe(): Promise<User> {
  const { data } = await apiClient.get<User>('/users/me')
  return data
}

import { apiPost, apiGet } from './client'

export interface UserProfile {
  user_id: string; username: string; display_name: string; student_id: string
}

export function login(username: string, password: string) {
  return apiPost<{ access_token: string; refresh_token: string; token_type: string }>(
    '/auth/login', { username, password })
}

export function fetchMe() {
  return apiGet<UserProfile>('/auth/me')
}

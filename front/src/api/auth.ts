import { apiPost, apiGet } from './client'

export interface UserProfile {
  user_id: string; username: string; display_name: string; student_id: string
}

export function login(username: string, password: string) {
  return apiPost<{ access_token: string; refresh_token: string; token_type: string }>(
    '/auth/login', { username, password })
}

export function register(username: string, password: string, display_name: string, student_id: string) {
  return apiPost<{ user_id: string; username: string; display_name: string }>(
    '/auth/register', { username, password, display_name, student_id })
}

export function fetchMe() {
  return apiGet<UserProfile>('/auth/me')
}

import { ref, computed } from 'vue'
import { login as apiLogin, fetchMe, type UserProfile } from '@/api/auth'

const user = ref<UserProfile | null>(null)
const loading = ref(false)

export function useAuth() {
  const isLoggedIn = computed(() => user.value !== null)

  async function checkAuth(): Promise<boolean> {
    const token = localStorage.getItem('access_token')
    if (!token) return false
    try {
      user.value = await fetchMe()
      return true
    } catch {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      return false
    }
  }

  async function login(username: string, password: string): Promise<void> {
    loading.value = true
    try {
      const resp = await apiLogin(username, password)
      localStorage.setItem('access_token', resp.access_token)
      localStorage.setItem('refresh_token', resp.refresh_token)
      user.value = await fetchMe()
    } finally {
      loading.value = false
    }
  }

  function logout() {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    user.value = null
  }

  return { user, isLoggedIn, loading, checkAuth, login, logout }
}

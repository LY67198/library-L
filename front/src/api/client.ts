function getToken(): string | null {
  return localStorage.getItem('access_token')
}

export async function apiGet<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(path, window.location.origin)
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v) url.searchParams.set(k, v)
    })
  }
  const headers: Record<string, string> = {}
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`

  const resp = await fetch(`/api/v1${url.pathname}${url.search}`, { headers })
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}))
    throw new Error(body.detail?.message || body.detail || `HTTP ${resp.status}`)
  }
  return resp.json()
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`

  const resp = await fetch(`/api/v1${path}`, {
    method: 'POST',
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!resp.ok) {
    const errBody = await resp.json().catch(() => ({}))
    throw new Error(errBody.detail?.message || errBody.detail || `HTTP ${resp.status}`)
  }
  return resp.json()
}

export async function apiDelete(path: string): Promise<void> {
  const headers: Record<string, string> = {}
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`

  const resp = await fetch(`/api/v1${path}`, { method: 'DELETE', headers })
  if (!resp.ok) {
    const errBody = await resp.json().catch(() => ({}))
    throw new Error(errBody.detail?.message || errBody.detail || `HTTP ${resp.status}`)
  }
}

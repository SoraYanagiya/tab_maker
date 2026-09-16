const BASE = '/api'

async function request(path, options = {}) {
  const response = await fetch(`${BASE}${path}`, {
    headers: options.body ? { 'Content-Type': 'application/json' } : undefined,
    ...options,
  })
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`
    try {
      const body = await response.json()
      if (body.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      // レスポンスがJSONでない場合はステータスをそのまま使う
    }
    throw new Error(detail)
  }
  return response.status === 204 ? null : response.json()
}

export const api = {
  listProjects: () => request('/projects'),
  createProject: (payload) => request('/projects', { method: 'POST', body: JSON.stringify(payload) }),
  getProject: (id) => request(`/projects/${id}`),
  updateProject: (id, payload) => request(`/projects/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteProject: (id) => request(`/projects/${id}`, { method: 'DELETE' }),
  duplicateProject: (id, name) =>
    request(`/projects/${id}/duplicate`, { method: 'POST', body: JSON.stringify({ name }) }),
  convert: (payload) => request('/convert', { method: 'POST', body: JSON.stringify(payload) }),
  importScore: async (file) => {
    const form = new FormData()
    form.append('file', file)
    const response = await fetch(`${BASE}/import`, { method: 'POST', body: form })
    if (!response.ok) {
      const body = await response.json().catch(() => ({}))
      throw new Error(body.detail || '読み込みに失敗しました')
    }
    return response.json()
  },
}

async function request(url, options = {}) {
  const res = await fetch(url, options)
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status}: ${text}`)
  }
  return res.json()
}

export async function fetchOpeningsReport(userPath) {
  return request(`/api/report/openings/${userPath}`)
}

export async function fetchOpeningsFiltered(userPath, eco, color) {
  return request(`/api/report/openings/${userPath}/${eco}/${color}`)
}

export async function fetchEndgamesReport(userPath) {
  return request(`/api/report/endgames/${userPath}`)
}

export async function fetchEndgamesAll(userPath, params = {}) {
  const qs = new URLSearchParams(params).toString()
  const url = `/api/report/endgames-all/${userPath}${qs ? '?' + qs : ''}`
  return request(url)
}

export async function fetchStatusJson(userPath) {
  return request(`/u/${userPath}/status/json`)
}

export async function cancelJob(userPath) {
  return request(`/u/${userPath}/status/cancel`, { method: 'POST' })
}

export async function renderBoards(userPath, specs) {
  return request(`/u/${userPath}/api/render-boards`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(specs),
  })
}

export async function submitFeedback(payload) {
  return request('/api/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}

export async function submitAnalysis(data) {
  return request('/analyze', {
    method: 'POST',
    headers: {
      'Accept': 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  })
}

export async function fetchAdminJobs() {
  return request('/api/admin/jobs')
}

export async function fetchAdminFeedback() {
  return request('/api/admin/feedback')
}

export async function fetchJobLogs(jobId) {
  return request(`/admin/jobs/${jobId}/logs`)
}

export async function fetchFlaskLogs(params = {}) {
  const qs = new URLSearchParams(params).toString()
  return request(`/admin/logs/flask${qs ? '?' + qs : ''}`)
}

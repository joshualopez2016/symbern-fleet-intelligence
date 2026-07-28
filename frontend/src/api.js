// Thin fetch helpers. All URLs are relative (/api/...) and proxied to FastAPI
// by the Vite dev server. A JWT (from login) is attached to every request; a
// 401 clears it and signals the app to return to the login screen.

const TOKEN_KEY = 'bms_token'
let _token = localStorage.getItem(TOKEN_KEY) || null

export function setAuthToken(t) {
  _token = t || null
  if (t) localStorage.setItem(TOKEN_KEY, t)
  else localStorage.removeItem(TOKEN_KEY)
}

export function getAuthToken() {
  return _token
}

function authHeaders(extra = {}) {
  return _token ? { ...extra, Authorization: `Bearer ${_token}` } : extra
}

async function getJSON(url) {
  const res = await fetch(url, { headers: authHeaders() })
  if (res.status === 401) {
    setAuthToken(null)
    window.dispatchEvent(new Event('bms-unauthorized'))
    throw new Error('Session expired')
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail || detail
    } catch {
      /* non-JSON error body */
    }
    throw new Error(`${res.status} ${detail}`)
  }
  return res.json()
}

async function sendJSON(method, url, body) {
  const opts = { method, headers: authHeaders(body !== undefined ? { 'Content-Type': 'application/json' } : {}) }
  if (body !== undefined) opts.body = JSON.stringify(body)
  const res = await fetch(url, opts)
  if (res.status === 401) {
    setAuthToken(null)
    window.dispatchEvent(new Event('bms-unauthorized'))
    throw new Error('Session expired')
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail || detail
    } catch {
      /* non-JSON */
    }
    throw new Error(detail)
  }
  return res.status === 204 ? null : res.json()
}

// --- auth ---
export async function login(email, password) {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) {
    let detail = 'Login failed'
    try {
      detail = (await res.json()).detail || detail
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  const data = await res.json()
  setAuthToken(data.token)
  return data.user
}

export function fetchMe() {
  return getJSON('/api/auth/me')
}

export async function logout() {
  try {
    await fetch('/api/auth/logout', { method: 'POST', headers: authHeaders() })
  } catch {
    /* ignore network errors on logout */
  }
  setAuthToken(null)
}

// --- data ---
export function fetchFleet(params = {}) {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') qs.set(k, v)
  }
  const q = qs.toString()
  return getJSON(`/api/fleet${q ? `?${q}` : ''}`)
}

export function fetchFleetSummary() {
  return getJSON('/api/fleet/summary')
}

export function fetchDevice(id) {
  return getJSON(`/api/devices/${encodeURIComponent(id)}`)
}

export function fetchReadings(id, { since, limit } = {}) {
  const qs = new URLSearchParams()
  if (since) qs.set('since', since)
  if (limit) qs.set('limit', limit)
  const q = qs.toString()
  return getJSON(`/api/devices/${encodeURIComponent(id)}/readings${q ? `?${q}` : ''}`)
}

export function fetchAlarms(params = {}) {
  const qs = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== '') qs.set(k, v)
  }
  const q = qs.toString()
  return getJSON(`/api/alarms${q ? `?${q}` : ''}`)
}

export function fetchThresholds() {
  return getJSON('/api/config/thresholds')
}

// --- notes (per-user CRUD) ---
export function listNotes(deviceId) {
  return getJSON(`/api/devices/${encodeURIComponent(deviceId)}/notes`)
}
export function createNote(deviceId, body) {
  return sendJSON('POST', `/api/devices/${encodeURIComponent(deviceId)}/notes`, { body })
}
export function updateNote(id, body) {
  return sendJSON('PUT', `/api/notes/${id}`, { body })
}
export function deleteNote(id) {
  return sendJSON('DELETE', `/api/notes/${id}`)
}

// --- reporting & export ---
export function fetchDailyReport(date) {
  return getJSON(`/api/daily-report${date ? `?date=${encodeURIComponent(date)}` : ''}`)
}

async function downloadFile(url, filename) {
  const res = await fetch(url, { headers: authHeaders() })
  if (res.status === 401) {
    setAuthToken(null)
    window.dispatchEvent(new Event('bms-unauthorized'))
    throw new Error('Session expired')
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail || detail
    } catch {
      /* binary/error */
    }
    throw new Error(detail)
  }
  const blob = await res.blob()
  const objUrl = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = objUrl
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(objUrl)
}

export function exportFleet(fmt, { status, site, q } = {}) {
  const p = new URLSearchParams()
  if (status && status !== 'all') p.set('status', status)
  if (site) p.set('site', site)
  if (q) p.set('q', q)
  const qs = p.toString()
  return downloadFile(`/api/export/fleet.${fmt}${qs ? `?${qs}` : ''}`, `fleet.${fmt}`)
}

export function exportDailyReport(fmt, date) {
  const qs = date ? `?date=${encodeURIComponent(date)}` : ''
  return downloadFile(`/api/export/daily-report.${fmt}${qs}`, `daily_pack_report.${fmt}`)
}

// --- AI ---
export function aiStatus() {
  return getJSON('/api/ai/status')
}
export function aiSearch(query) {
  return sendJSON('POST', '/api/ai/search', { query })
}
export function aiBriefing() {
  return sendJSON('POST', '/api/ai/briefing', {})
}

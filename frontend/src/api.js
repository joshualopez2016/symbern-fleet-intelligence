// Thin fetch helpers. All URLs are relative (/api/...) and proxied to FastAPI
// by the Vite dev server, so there is no backend host hardcoded here.

async function getJSON(url) {
  const res = await fetch(url)
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

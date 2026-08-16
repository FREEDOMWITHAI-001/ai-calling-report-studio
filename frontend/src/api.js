const BASE = '/api'

/**
 * Client scoping.
 *
 * The backend now *requires* `client_id` on every data route, so the UI keeps
 * the active client here and stamps it onto each request. This is the only
 * place that decides which org a call is for — no page passes its own.
 */
let activeClientId = null

export function setActiveClient(id) {
  activeClientId = id ?? null
}

export function getActiveClient() {
  return activeClientId
}

/** Appends `client_id` to a path, refusing to fire an unscoped request. */
function scoped(path) {
  if (!activeClientId) throw new Error('No client selected')
  return `${path}${path.includes('?') ? '&' : '?'}client_id=${activeClientId}`
}

/**
 * Turns any FastAPI error body into one readable sentence.
 *
 * `detail` is a string for our own HTTPExceptions, but a list of
 * `{loc, msg, type}` objects for 422 validation failures. Passing that list
 * straight to `new Error()` is what produced "[object Object]" on screen.
 */
function describeError(body, fallback) {
  const detail = body?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const parts = detail.map((d) => {
      const field = Array.isArray(d?.loc) ? d.loc.filter((p) => p !== 'body' && p !== 'query').join('.') : ''
      const msg = d?.msg || d?.type || 'invalid'
      return field ? `${field}: ${msg}` : msg
    })
    return parts.join('; ') || fallback
  }
  if (detail && typeof detail === 'object') return JSON.stringify(detail)
  return fallback
}

async function request(path, options = {}) {
  let response
  try {
    response = await fetch(`${BASE}${path}`, {
      headers: options.body instanceof FormData ? undefined : { 'Content-Type': 'application/json' },
      ...options,
    })
  } catch {
    throw new Error('Cannot reach the API. Is the server running on port 8000?')
  }

  if (!response.ok) {
    const fallback = `${response.status} ${response.statusText || 'Request failed'}`
    let message = fallback
    try {
      message = describeError(await response.json(), fallback)
    } catch { /* non-JSON error body — keep the status line */ }
    const error = new Error(message)
    error.status = response.status
    throw error
  }

  if (response.status === 204) return null
  return response.json()
}

export const api = {
  health: () => request('/health'),

  // Not client-scoped: this is the list you pick a client *from*.
  clients: () => request('/clients'),

  summary: () => request(scoped('/summary')),
  bots: () => request(scoped('/bots')),
  updateBot: (id, body) => request(scoped(`/bots/${id}`), { method: 'PATCH', body: JSON.stringify(body) }),
  rows: (table, limit = 50, offset = 0) => request(scoped(`/rows/${table}?limit=${limit}&offset=${offset}`)),

  datasets: () => request('/uploads/datasets'),
  uploads: () => request(scoped('/uploads')),
  upload: (file) => {
    if (!activeClientId) throw new Error('No client selected')
    const form = new FormData()
    form.append('file', file)
    form.append('client_id', String(activeClientId))
    return request('/uploads', { method: 'POST', body: form })
  },
  preview: (id, sheet) =>
    request(scoped(`/uploads/${id}/preview${sheet ? `?sheet=${encodeURIComponent(sheet)}` : ''}`)),
  ingest: (id, body) => request(scoped(`/uploads/${id}/ingest`), { method: 'POST', body: JSON.stringify(body) }),
  uploadStatus: (id) => request(scoped(`/uploads/${id}`)),
  deleteUpload: (id) => request(scoped(`/uploads/${id}`), { method: 'DELETE' }),

  methodologies: () => request('/methodologies'),
  methodologyDefaults: () => request('/methodologies/defaults'),
  saveMethodology: (body) => request('/methodologies', { method: 'POST', body: JSON.stringify(body) }),

  // Report formats — a client's own layouts, plus the built-ins as fallbacks.
  formats: () => request(scoped('/report-formats')),
  builtInFormats: () => request('/report-formats/built-in'),
  sectionLibrary: () => request('/report-formats/library'),
  saveFormat: (body) => request(scoped('/report-formats'), { method: 'POST', body: JSON.stringify(body) }),
  makeFormatDefault: (id) => request(scoped(`/report-formats/${id}/default`), { method: 'POST' }),
  deleteFormat: (id) => request(scoped(`/report-formats/${id}`), { method: 'DELETE' }),

  presets: () => request('/reports/presets/ranges'),
  previewReport: (body) => request('/reports/preview', { method: 'POST', body: JSON.stringify({ ...body, client_id: body.client_id ?? activeClientId }) }),
  createReport: (body) => request('/reports', { method: 'POST', body: JSON.stringify({ ...body, client_id: body.client_id ?? activeClientId }) }),
  createBatch: (ranges) =>
    request('/reports/batch', {
      method: 'POST',
      body: JSON.stringify({ ranges: ranges.map((r) => ({ ...r, client_id: r.client_id ?? activeClientId })) }),
    }),
  reports: () => request(scoped('/reports')),
  report: (id) => request(scoped(`/reports/${id}`)),
  deleteReport: (id) => request(scoped(`/reports/${id}`), { method: 'DELETE' }),
  downloadUrl: (id, format) => `${BASE}/reports/${id}/download/${format}?client_id=${activeClientId}`,
}

export const fmt = {
  money: (v, decimals = 0) =>
    v === null || v === undefined ? '—' : `₹${Number(v).toLocaleString('en-IN', { maximumFractionDigits: decimals, minimumFractionDigits: decimals })}`,
  pct: (v, decimals = 1) => (v === null || v === undefined ? '—' : `${(v * 100).toFixed(decimals)}%`),
  delta: (v, decimals = 1) =>
    v === null || v === undefined ? '—' : `${v >= 0 ? '+' : ''}${(v * 100).toFixed(decimals)}%`,
  multiple: (v) => (v === null || v === undefined ? '—' : `${Number(v).toFixed(1)}×`),
  number: (v, decimals = 0) =>
    v === null || v === undefined ? '—' : Number(v).toLocaleString('en-IN', { maximumFractionDigits: decimals, minimumFractionDigits: decimals }),
  compact: (v) => {
    if (v === null || v === undefined) return '—'
    const n = Number(v)
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}m`
    if (n >= 1_000) return `${Math.round(n / 1_000)}k`
    return String(n)
  },
  date: (iso) => (iso ? new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'),
  dateTime: (iso) => (iso ? new Date(iso).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' }) : '—'),
}

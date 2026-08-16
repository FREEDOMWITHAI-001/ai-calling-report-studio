import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { ThemeProvider } from '@mui/material/styles'
import CssBaseline from '@mui/material/CssBaseline'
import GlobalStyles from '@mui/material/GlobalStyles'
import { buildTheme } from '../theme/index.js'
import { cssVars } from '../theme/tokens.js'
import { api, setActiveClient } from '../api.js'

const Ctx = createContext(null)

/** Everything the shell needs: theme, selected client, date range, filters. */
export function useApp() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useApp must be used inside <AppState>')
  return ctx
}

const KEY = 'rs.v1'

function load() {
  try {
    return JSON.parse(localStorage.getItem(KEY)) || {}
  } catch {
    return {}
  }
}

function save(patch) {
  try {
    localStorage.setItem(KEY, JSON.stringify({ ...load(), ...patch }))
  } catch {
    /* private mode — settings just do not persist */
  }
}

const iso = (d) => d.toISOString().slice(0, 10)
const shift = (isoDate, days) => {
  const d = new Date(`${isoDate}T00:00:00`)
  d.setDate(d.getDate() + days)
  return iso(d)
}

export const PRESETS = [
  { id: 'last7', label: 'Last 7 days', days: 7 },
  { id: 'last14', label: 'Last 14 days', days: 14 },
  { id: 'last30', label: 'Last 30 days', days: 30 },
  { id: 'last90', label: 'Last 90 days', days: 90 },
  { id: 'reference', label: 'Reference window', from: '2026-07-17', to: '2026-08-14' },
  { id: 'all', label: 'All data' },
]

export default function AppState({ children }) {
  const saved = load()

  // ---- theme -------------------------------------------------------------
  const [mode, setMode] = useState(() => {
    if (saved.mode === 'light' || saved.mode === 'dark') return saved.mode
    return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  })
  const toggleMode = useCallback(() => {
    setMode((m) => {
      const next = m === 'dark' ? 'light' : 'dark'
      save({ mode: next })
      return next
    })
  }, [])
  const theme = useMemo(() => buildTheme(mode), [mode])

  // ---- clients -----------------------------------------------------------
  const [clients, setClients] = useState([])
  const [clientId, setClientIdRaw] = useState(() => {
    // Stamp the api module before anything can fire a scoped request.
    setActiveClient(saved.clientId ?? null)
    return saved.clientId ?? null
  })
  const setClientId = useCallback((id) => {
    setActiveClient(id)
    setClientIdRaw(id)
    save({ clientId: id })
  }, [])

  // ---- date range --------------------------------------------------------
  const [bounds, setBounds] = useState(null) // { min, max } across the fact tables
  const [range, setRangeRaw] = useState(saved.range ?? null)
  const setRange = useCallback((next) => {
    setRangeRaw(next)
    save({ range: next })
  }, [])

  const applyPreset = useCallback(
    (preset) => {
      if (preset.id === 'all') {
        if (!bounds) return
        setRange({ from: bounds.min, to: bounds.max, preset: 'all' })
        return
      }
      if (preset.from) {
        setRange({ from: preset.from, to: preset.to, preset: preset.id })
        return
      }
      const to = bounds?.max || iso(new Date())
      setRange({ from: shift(to, -(preset.days - 1)), to, preset: preset.id })
    },
    [bounds, setRange],
  )

  // ---- filters -----------------------------------------------------------
  const [filters, setFiltersRaw] = useState(saved.filters ?? { language: null, program: null })
  const setFilters = useCallback((next) => {
    setFiltersRaw(next)
    save({ filters: next })
  }, [])

  // ---- command palette ---------------------------------------------------
  const [paletteOpen, setPaletteOpen] = useState(false)

  // ---- bootstrap ---------------------------------------------------------
  const [ready, setReady] = useState(false)
  const [bootError, setBootError] = useState(null)

  useEffect(() => {
    let alive = true
    // Clients first — a scoped call cannot be made until one is chosen.
    api.clients()
      .then(async (clientList) => {
        if (!alive) return null
        setClients(clientList)

        // Keep the saved client only if it still exists.
        const valid = clientList.some((c) => c.id === saved.clientId)
        const active = valid ? saved.clientId : clientList[0]?.id ?? null
        setActiveClient(active)
        if (!valid) setClientIdRaw(active)
        if (!active) throw new Error('No clients exist yet. Seed them first.')

        return api.summary()
      })
      .then((summary) => {
        if (!alive || !summary) return
        const dates = Object.values(summary.tables || {})
          .flatMap((t) => [t.min_date, t.max_date])
          .filter(Boolean)
          .sort()
        const b = dates.length ? { min: dates[0], max: dates[dates.length - 1] } : null
        setBounds(b)

        if (!saved.range && b) {
          setRangeRaw({ from: shift(b.max, -29), to: b.max, preset: 'last30' })
        }
        setReady(true)
      })
      .catch((e) => {
        if (!alive) return
        setBootError(e.message)
        setReady(true)
      })
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // A different client has a different date span — refresh the bounds so the
  // presets ("All data", "Last 30 days") describe *this* org's data.
  useEffect(() => {
    if (!ready || !clientId) return
    let alive = true
    api.summary()
      .then((summary) => {
        if (!alive) return
        const dates = Object.values(summary.tables || {})
          .flatMap((t) => [t.min_date, t.max_date])
          .filter(Boolean)
          .sort()
        setBounds(dates.length ? { min: dates[0], max: dates[dates.length - 1] } : null)
      })
      .catch(() => { if (alive) setBounds(null) })
    return () => { alive = false }
  }, [clientId, ready])

  const client = clients.find((c) => c.id === clientId) || null

  const value = useMemo(
    () => ({
      mode, toggleMode,
      clients, client, clientId, setClientId,
      range, setRange, applyPreset, bounds,
      filters, setFilters,
      paletteOpen, setPaletteOpen,
      ready, bootError,
    }),
    [mode, toggleMode, clients, client, clientId, setClientId, range, setRange,
      applyPreset, bounds, filters, setFilters, paletteOpen, ready, bootError],
  )

  return (
    <Ctx.Provider value={value}>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <GlobalStyles styles={{ ':root': cssVars(mode) }} />
        {children}
      </ThemeProvider>
    </Ctx.Provider>
  )
}

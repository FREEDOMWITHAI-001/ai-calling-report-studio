import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Box, Dialog, InputBase, Stack, Typography, useTheme } from '@mui/material'
import SearchRoundedIcon from '@mui/icons-material/SearchRounded'
import BusinessRoundedIcon from '@mui/icons-material/BusinessRounded'
import DescriptionRoundedIcon from '@mui/icons-material/DescriptionRounded'
import BoltRoundedIcon from '@mui/icons-material/BoltRounded'
import { useApp } from '../state/AppState.jsx'
import { NAV, NAV_CONFIG } from './shell/Shell.jsx'
import { FONT_MONO } from '../theme/tokens.js'
import { api, fmt } from '../api.js'

/** Subsequence match — "fwa" finds "Freedom With AI". */
function score(query, text) {
  const q = query.toLowerCase()
  const t = text.toLowerCase()
  if (!q) return 1
  if (t.startsWith(q)) return 1000
  const direct = t.indexOf(q)
  if (direct >= 0) return 500 - direct
  let i = 0
  for (const ch of t) if (ch === q[i]) i += 1
  return i === q.length ? 100 : 0
}

export default function CommandPalette() {
  const { palette } = useTheme()
  const navigate = useNavigate()
  const { paletteOpen, setPaletteOpen, clients, setClientId } = useApp()
  const [query, setQuery] = useState('')
  const [cursor, setCursor] = useState(0)
  const [reports, setReports] = useState([])
  const listRef = useRef(null)

  // Ctrl/Cmd K from anywhere.
  useEffect(() => {
    const onKey = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setPaletteOpen((o) => !o)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [setPaletteOpen])

  useEffect(() => {
    if (!paletteOpen) return
    setQuery('')
    setCursor(0)
    api.reports().then(setReports).catch(() => setReports([]))
  }, [paletteOpen])

  const items = useMemo(() => {
    const all = [
      ...[...NAV, ...NAV_CONFIG].map((n) => ({
        group: 'Pages', label: n.label, icon: n.icon, run: () => navigate(n.path),
      })),
      ...clients.map((c) => ({
        group: 'Clients', label: c.name, tail: 'switch client', icon: BusinessRoundedIcon,
        run: () => { setClientId(c.id); navigate('/overview') },
      })),
      ...reports.map((r) => ({
        group: 'Reports', label: r.title, tail: fmt.date(r.date_to), icon: DescriptionRoundedIcon,
        run: () => navigate(`/reports/${r.id}`),
      })),
      { group: 'Actions', label: 'Generate a report', tail: 'Ctrl G', icon: BoltRoundedIcon, run: () => navigate('/reports?new=1') },
      { group: 'Actions', label: 'Upload a file', tail: 'Ctrl U', icon: BoltRoundedIcon, run: () => navigate('/ingest') },
    ]
    return all
      .map((it) => ({ ...it, s: score(query, it.label) }))
      .filter((it) => it.s > 0)
      .sort((a, b) => b.s - a.s)
      .slice(0, 24)
  }, [query, clients, reports, navigate, setClientId])

  const grouped = useMemo(() => {
    const out = []
    let last = null
    items.forEach((it, i) => {
      if (it.group !== last) { out.push({ header: it.group }); last = it.group }
      out.push({ ...it, index: i })
    })
    return out
  }, [items])

  const close = () => setPaletteOpen(false)
  const runAt = (i) => { const it = items[i]; if (it) { close(); it.run() } }

  const onKeyDown = (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setCursor((c) => Math.min(c + 1, items.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setCursor((c) => Math.max(c - 1, 0)) }
    else if (e.key === 'Enter') { e.preventDefault(); runAt(cursor) }
  }

  useEffect(() => {
    listRef.current?.querySelector('[data-sel="1"]')?.scrollIntoView({ block: 'nearest' })
  }, [cursor])

  return (
    <Dialog
      open={paletteOpen}
      onClose={close}
      fullWidth
      maxWidth="sm"
      slotProps={{ paper: { sx: { mt: '-14vh', alignSelf: 'flex-start', overflow: 'hidden' } } }}
    >
      <Stack direction="row" alignItems="center" gap={1.25} sx={{ px: 2, py: 1.5, borderBottom: `1px solid ${palette.t.border}` }}>
        <SearchRoundedIcon sx={{ fontSize: 18, color: palette.t.faint }} />
        <InputBase
          autoFocus
          fullWidth
          value={query}
          onChange={(e) => { setQuery(e.target.value); setCursor(0) }}
          onKeyDown={onKeyDown}
          placeholder="Jump to a client, report or action…"
          sx={{ fontSize: 14.5 }}
        />
        <Box component="span" sx={{ fontFamily: FONT_MONO, fontSize: 10, color: palette.t.faint, border: `1px solid ${palette.t.border}`, borderRadius: '5px', px: 0.75 }}>
          Esc
        </Box>
      </Stack>

      <Box ref={listRef} sx={{ maxHeight: 360, overflowY: 'auto', py: 0.5 }}>
        {!items.length && (
          <Typography sx={{ px: 2, py: 3, fontSize: 13, color: palette.t.muted, textAlign: 'center' }}>
            Nothing matches “{query}”.
          </Typography>
        )}
        {grouped.map((row, i) =>
          row.header ? (
            <Typography key={`h-${row.header}-${i}`} sx={{ px: 2, pt: 1.4, pb: 0.5, fontFamily: FONT_MONO, fontSize: 9.5, letterSpacing: '.13em', textTransform: 'uppercase', color: palette.t.faint, fontWeight: 600 }}>
              {row.header}
            </Typography>
          ) : (
            <Stack
              key={`i-${row.group}-${row.label}-${row.index}`}
              direction="row"
              alignItems="center"
              gap={1.25}
              data-sel={row.index === cursor ? '1' : '0'}
              onMouseEnter={() => setCursor(row.index)}
              onClick={() => runAt(row.index)}
              sx={{
                px: 2, py: 1, fontSize: 13, cursor: 'pointer',
                background: row.index === cursor ? palette.t.accentSoft : 'transparent',
                color: row.index === cursor ? palette.t.accent : palette.t.text,
                fontWeight: row.index === cursor ? 600 : 500,
              }}
            >
              <row.icon sx={{ fontSize: 16, flex: 'none' }} />
              <Box sx={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{row.label}</Box>
              {row.tail && (
                <Box component="span" sx={{ ml: 'auto', pl: 2, fontFamily: FONT_MONO, fontSize: 10.5, color: palette.t.faint, whiteSpace: 'nowrap' }}>
                  {row.tail}
                </Box>
              )}
            </Stack>
          ),
        )}
      </Box>
    </Dialog>
  )
}

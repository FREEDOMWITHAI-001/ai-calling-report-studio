import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  Box, Button, Divider, IconButton, Menu, MenuItem, Stack, TextField, Tooltip, Typography, useTheme,
} from '@mui/material'
import GridViewRoundedIcon from '@mui/icons-material/GridViewRounded'
import TableRowsRoundedIcon from '@mui/icons-material/TableRowsRounded'
import FileUploadRoundedIcon from '@mui/icons-material/FileUploadRounded'
import DescriptionRoundedIcon from '@mui/icons-material/DescriptionRounded'
import TuneRoundedIcon from '@mui/icons-material/TuneRounded'
import DarkModeRoundedIcon from '@mui/icons-material/DarkModeRounded'
import LightModeRoundedIcon from '@mui/icons-material/LightModeRounded'
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded'
import CalendarTodayRoundedIcon from '@mui/icons-material/CalendarTodayRounded'
import CheckRoundedIcon from '@mui/icons-material/CheckRounded'
import GraphicEqRoundedIcon from '@mui/icons-material/GraphicEqRounded'
import { PRESETS, useApp } from '../../state/AppState.jsx'
import { FONT_MONO } from '../../theme/tokens.js'
import { fmt } from '../../api.js'

const NAV = [
  { path: '/overview', label: 'Overview', icon: GridViewRoundedIcon },
  { path: '/data', label: 'Data', icon: TableRowsRoundedIcon },
  { path: '/ingest', label: 'Ingest', icon: FileUploadRoundedIcon },
  { path: '/reports', label: 'Reports', icon: DescriptionRoundedIcon },
]
const NAV_CONFIG = [
  { path: '/formats', label: 'Report formats', icon: DescriptionRoundedIcon },
  { path: '/methodology', label: 'Methodology', icon: TuneRoundedIcon },
]

const SIDEBAR_W = 216

/* ---------------------------------------------------------------- */

function ClientSwitcher() {
  const { palette } = useTheme()
  const { clients, client, setClientId } = useApp()
  const [anchor, setAnchor] = useState(null)

  return (
    <>
      <Box
        component="button"
        type="button"
        onClick={(e) => setAnchor(e.currentTarget)}
        sx={{
          display: 'flex', alignItems: 'center', gap: 1, cursor: 'pointer', font: 'inherit',
          border: `1px solid ${palette.t.border}`, background: palette.t.panel2, color: palette.t.text,
          borderRadius: '8px', px: 1.15, py: 0.6, fontSize: 12.5, fontWeight: 580,
          '&:hover': { borderColor: palette.t.borderStrong, background: palette.t.panel3 },
        }}
      >
        <Box sx={{
          width: 18, height: 18, borderRadius: '5px', display: 'grid', placeItems: 'center',
          background: palette.t.accentSoft, color: palette.t.accent, fontSize: 10, fontWeight: 700, flex: 'none',
        }}>
          {(client?.name || '?')[0].toUpperCase()}
        </Box>
        <Box sx={{ maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {client?.name || 'Select client'}
        </Box>
        <ExpandMoreRoundedIcon sx={{ fontSize: 15, opacity: 0.55 }} />
      </Box>

      <Menu anchorEl={anchor} open={!!anchor} onClose={() => setAnchor(null)} slotProps={{ paper: { sx: { minWidth: 244, maxHeight: 420 } } }}>
        <Typography sx={{ px: 2, pt: 1, pb: 0.5, fontFamily: FONT_MONO, fontSize: 9.5, letterSpacing: '.13em', textTransform: 'uppercase', color: palette.t.faint, fontWeight: 600 }}>
          Switch client
        </Typography>
        {clients.map((c) => (
          <MenuItem key={c.id} selected={c.id === client?.id} onClick={() => { setClientId(c.id); setAnchor(null) }}>
            <Box sx={{
              width: 18, height: 18, borderRadius: '5px', display: 'grid', placeItems: 'center', mr: 1.25,
              background: palette.t.accentSoft, color: palette.t.accent, fontSize: 10, fontWeight: 700, flex: 'none',
            }}>
              {c.name[0].toUpperCase()}
            </Box>
            <Box sx={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis' }}>{c.name}</Box>
            {c.id === client?.id && <CheckRoundedIcon sx={{ fontSize: 15, color: palette.t.accent, ml: 1 }} />}
          </MenuItem>
        ))}
      </Menu>
    </>
  )
}

/* ---------------------------------------------------------------- */

function RangePicker() {
  const { palette } = useTheme()
  const { range, setRange, applyPreset, bounds } = useApp()
  const [anchor, setAnchor] = useState(null)

  const label = range ? `${fmt.date(range.from)} – ${fmt.date(range.to)}` : 'No range'

  return (
    <>
      <Box
        component="button"
        type="button"
        onClick={(e) => setAnchor(e.currentTarget)}
        sx={{
          display: 'flex', alignItems: 'center', gap: 0.9, cursor: 'pointer', font: 'inherit',
          border: `1px solid ${palette.t.border}`, background: palette.t.panel2, color: palette.t.muted,
          borderRadius: 999, px: 1.25, py: 0.5, fontSize: 11.5, fontWeight: 560, whiteSpace: 'nowrap',
          '&:hover': { borderColor: palette.t.borderStrong, color: palette.t.text },
        }}
      >
        <CalendarTodayRoundedIcon sx={{ fontSize: 13 }} />
        {label}
      </Box>

      <Menu anchorEl={anchor} open={!!anchor} onClose={() => setAnchor(null)} slotProps={{ paper: { sx: { minWidth: 258 } } }}>
        {PRESETS.map((p) => (
          <MenuItem
            key={p.id}
            selected={range?.preset === p.id}
            disabled={p.id === 'all' && !bounds}
            onClick={() => { applyPreset(p); setAnchor(null) }}
          >
            {p.label}
            {p.id === 'reference' && (
              <Box component="span" sx={{ ml: 'auto', pl: 2, fontSize: 10.5, color: palette.t.faint, fontFamily: FONT_MONO }}>validated</Box>
            )}
          </MenuItem>
        ))}
        <Divider sx={{ my: 0.75 }} />
        <Stack direction="row" gap={1} sx={{ px: 1.5, py: 1 }}>
          <TextField
            size="small" type="date" label="From" InputLabelProps={{ shrink: true }}
            value={range?.from || ''}
            onChange={(e) => setRange({ ...range, from: e.target.value, preset: 'custom' })}
          />
          <TextField
            size="small" type="date" label="To" InputLabelProps={{ shrink: true }}
            value={range?.to || ''}
            onChange={(e) => setRange({ ...range, to: e.target.value, preset: 'custom' })}
          />
        </Stack>
      </Menu>
    </>
  )
}

/* ---------------------------------------------------------------- */

function NavLink({ item, tail }) {
  const { palette } = useTheme()
  const location = useLocation()
  const active = location.pathname.startsWith(item.path)
  const Icon = item.icon

  return (
    <Box
      component={Link}
      to={item.path}
      sx={{
        display: 'flex', alignItems: 'center', gap: 1.25, px: 1.15, py: 0.9, borderRadius: '8px',
        textDecoration: 'none', fontSize: 12.5, fontWeight: active ? 620 : 540,
        color: active ? palette.t.accent : palette.t.muted,
        background: active ? palette.t.accentSoft : 'transparent',
        '&:hover': { background: active ? palette.t.accentSoft : palette.t.panel2, color: active ? palette.t.accent : palette.t.text },
      }}
    >
      <Icon sx={{ fontSize: 17 }} />
      {item.label}
      {tail != null && (
        <Box component="span" sx={{ ml: 'auto', fontSize: 10.5, fontFamily: FONT_MONO, color: palette.t.faint }}>{tail}</Box>
      )}
    </Box>
  )
}

/* ---------------------------------------------------------------- */

export default function Shell({ children, counts = {} }) {
  const { palette } = useTheme()
  const { mode, toggleMode, setPaletteOpen } = useApp()

  return (
    <Box sx={{ minHeight: '100vh', display: 'grid', gridTemplateColumns: { xs: '1fr', md: `${SIDEBAR_W}px 1fr` }, background: palette.t.bg }}>
      {/* sidebar */}
      <Box
        component="aside"
        sx={{
          display: { xs: 'none', md: 'flex' }, flexDirection: 'column', gap: 0.4,
          background: palette.t.panel, borderRight: `1px solid ${palette.t.border}`,
          px: 1.25, py: 1.75, position: 'sticky', top: 0, height: '100vh',
        }}
      >
        <Stack direction="row" alignItems="center" gap={1.25} sx={{ px: 1, pb: 1.75 }}>
          <Box sx={{ width: 24, height: 24, borderRadius: '7px', background: palette.t.btnBg, display: 'grid', placeItems: 'center', flex: 'none' }}>
            <GraphicEqRoundedIcon sx={{ fontSize: 15, color: palette.t.btnFg }} />
          </Box>
          <Typography sx={{ fontSize: 13.5, fontWeight: 640, letterSpacing: '-.01em' }}>Report Studio</Typography>
        </Stack>

        {NAV.map((item) => <NavLink key={item.path} item={item} tail={counts[item.path]} />)}

        <Typography sx={{ px: 1.15, pt: 2, pb: 0.75, fontFamily: FONT_MONO, fontSize: 9.5, letterSpacing: '.13em', textTransform: 'uppercase', color: palette.t.faint, fontWeight: 600 }}>
          Configure
        </Typography>
        {NAV_CONFIG.map((item) => <NavLink key={item.path} item={item} />)}

        <Box sx={{ flex: 1 }} />
        <Box
          component="button"
          type="button"
          onClick={() => setPaletteOpen(true)}
          sx={{
            display: 'flex', alignItems: 'center', gap: 1, cursor: 'pointer', font: 'inherit', width: '100%',
            border: `1px solid ${palette.t.border}`, background: palette.t.panel2, color: palette.t.faint,
            borderRadius: '8px', px: 1.15, py: 0.75, fontSize: 12,
            '&:hover': { color: palette.t.text, borderColor: palette.t.borderStrong },
          }}
        >
          Search…
          <Box component="span" sx={{ ml: 'auto', fontFamily: FONT_MONO, fontSize: 10, border: `1px solid ${palette.t.border}`, borderRadius: '5px', px: 0.75, py: '1px' }}>
            Ctrl K
          </Box>
        </Box>
      </Box>

      {/* main column */}
      <Box sx={{ minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        <Stack
          direction="row" alignItems="center" gap={1.25}
          sx={{
            px: 2, py: 1.25, background: palette.t.panel, borderBottom: `1px solid ${palette.t.border}`,
            flexWrap: 'wrap', position: 'sticky', top: 0, zIndex: 10,
          }}
        >
          <ClientSwitcher />
          <RangePicker />
          <Box sx={{ flex: 1 }} />
          <Tooltip title="Search — Ctrl K">
            <IconButton size="small" onClick={() => setPaletteOpen(true)} sx={{ display: { xs: 'inline-flex', md: 'none' } }}>
              <Box component="span" sx={{ fontFamily: FONT_MONO, fontSize: 11 }}>⌘K</Box>
            </IconButton>
          </Tooltip>
          <Tooltip title={mode === 'dark' ? 'Switch to light' : 'Switch to dark'}>
            <IconButton size="small" onClick={toggleMode} aria-label="Toggle theme">
              {mode === 'dark' ? <LightModeRoundedIcon sx={{ fontSize: 17 }} /> : <DarkModeRoundedIcon sx={{ fontSize: 17 }} />}
            </IconButton>
          </Tooltip>
          <Box sx={{
            width: 27, height: 27, borderRadius: 99, display: 'grid', placeItems: 'center',
            background: palette.t.panel3, color: palette.t.muted, border: `1px solid ${palette.t.border}`,
            fontSize: 10.5, fontWeight: 700,
          }}>
            AP
          </Box>
        </Stack>

        <Box sx={{ p: { xs: 1.75, md: 2.5 }, flex: 1, minWidth: 0 }}>{children}</Box>
      </Box>
    </Box>
  )
}

export { NAV, NAV_CONFIG }

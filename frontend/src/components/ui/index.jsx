import { Box, Stack, Typography, useTheme } from '@mui/material'
import { FONT_MONO } from '../../theme/tokens.js'
import { fmt } from '../../api.js'

/* ------------------------------------------------------------------ *
 * HGrid — the structural motif. Children sit on a border-coloured bed
 * with 1px gaps, so panels share hairlines instead of floating as cards.
 * ------------------------------------------------------------------ */
export function HGrid({ columns = 1, children, sx, ...rest }) {
  const { palette } = useTheme()
  return (
    <Box
      sx={{
        display: 'grid',
        gap: '1px',
        background: palette.t.border,
        border: `1px solid ${palette.t.border}`,
        borderRadius: '12px',
        overflow: 'hidden',
        gridTemplateColumns: typeof columns === 'number' ? `repeat(${columns}, 1fr)` : columns,
        '& > *': { background: palette.t.panel, minWidth: 0 },
        ...sx,
      }}
      {...rest}
    >
      {children}
    </Box>
  )
}

/* ------------------------------------------------------------------ *
 * Panel — a titled surface. `flush` removes body padding for tables.
 * ------------------------------------------------------------------ */
export function Panel({ title, action, children, flush = false, sx }) {
  const { palette } = useTheme()
  return (
    <Box
      sx={{
        background: palette.t.panel,
        border: `1px solid ${palette.t.border}`,
        borderRadius: '12px',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        minWidth: 0,
        ...sx,
      }}
    >
      {(title || action) && (
        <Stack
          direction="row"
          alignItems="center"
          gap={1}
          sx={{ px: 1.75, py: 1.25, borderBottom: `1px solid ${palette.t.border}`, flexWrap: 'wrap' }}
        >
          <Typography variant="h6">{title}</Typography>
          <Box sx={{ flex: 1 }} />
          {action}
        </Stack>
      )}
      <Box sx={{ p: flush ? 0 : 1.75, flex: 1, minWidth: 0, overflowX: flush ? 'auto' : 'visible' }}>
        {children}
      </Box>
    </Box>
  )
}

/* ------------------------------------------------------------------ *
 * Label — the mono "instrument" voice used for eyebrows and column heads.
 * ------------------------------------------------------------------ */
export function Label({ children, sx }) {
  const { palette } = useTheme()
  return (
    <Box
      component="span"
      sx={{
        fontFamily: FONT_MONO,
        fontSize: 9.5,
        letterSpacing: '.13em',
        textTransform: 'uppercase',
        fontWeight: 600,
        color: palette.t.faint,
        ...sx,
      }}
    >
      {children}
    </Box>
  )
}

/* ------------------------------------------------------------------ *
 * Pill — semantic status. Tone is separate from the accent hue.
 * ------------------------------------------------------------------ */
const TONES = {
  neutral: ['panel2', 'muted', 'border'],
  accent: ['accentSoft', 'accent', 'accentLine'],
  pos: ['posSoft', 'pos', 'transparent'],
  warn: ['warnSoft', 'warn', 'transparent'],
  crit: ['critSoft', 'crit', 'transparent'],
}

export function Pill({ tone = 'neutral', dot = false, children, sx }) {
  const { palette } = useTheme()
  const [bg, fg, bd] = TONES[tone] || TONES.neutral
  return (
    <Box
      component="span"
      sx={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 0.75,
        px: 1.1,
        py: '3px',
        borderRadius: 999,
        fontSize: 11.5,
        fontWeight: 560,
        lineHeight: 1.4,
        whiteSpace: 'nowrap',
        background: palette.t[bg],
        color: palette.t[fg],
        border: `1px solid ${bd === 'transparent' ? 'transparent' : palette.t[bd]}`,
        ...sx,
      }}
    >
      {dot && <Box component="span" sx={{ width: 6, height: 6, borderRadius: 99, background: 'currentColor', flex: 'none' }} />}
      {children}
    </Box>
  )
}

/* ------------------------------------------------------------------ *
 * Delta — a signed change, coloured by direction, never by magnitude.
 * ------------------------------------------------------------------ */
export function Delta({ value, decimals = 1, suffix = '' }) {
  const { palette } = useTheme()
  if (value === null || value === undefined) {
    return <Box component="span" sx={{ color: palette.t.faint }}>—</Box>
  }
  const up = value >= 0
  return (
    <Box component="span" sx={{ color: up ? palette.t.pos : palette.t.crit, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
      {up ? '+' : ''}{(value * 100).toFixed(decimals)}%{suffix}
    </Box>
  )
}

/* ------------------------------------------------------------------ *
 * Sparkline — an area fill, a line, and an emphasised endpoint.
 * ------------------------------------------------------------------ */
export function Sparkline({ points = [], width = 78, height = 26 }) {
  const { palette } = useTheme()
  const clean = points.filter((p) => Number.isFinite(p))
  if (clean.length < 2) return <Box sx={{ width, height }} />

  const pad = 2
  const min = Math.min(...clean)
  const max = Math.max(...clean)
  const span = max - min || 1
  const xy = clean.map((v, i) => [
    (i / (clean.length - 1)) * (width - pad * 2) + pad,
    height - pad - ((v - min) / span) * (height - pad * 2),
  ])
  const line = xy.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(' ')
  const area = `${line} L${width - pad} ${height} L${pad} ${height} Z`
  const last = xy[xy.length - 1]

  return (
    <Box component="svg" viewBox={`0 0 ${width} ${height}`} sx={{ width, height, display: 'block', flex: 'none' }} aria-hidden="true">
      <path d={area} fill={palette.t.accent} opacity={0.13} />
      <path d={line} fill="none" stroke={palette.t.accent} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={last[0]} cy={last[1]} r={2.3} fill={palette.t.accent} />
    </Box>
  )
}

/* ------------------------------------------------------------------ *
 * StatTile — headline number, its change, and the shape of how it got there.
 * ------------------------------------------------------------------ */
export function StatTile({ label, value, tone = 'neutral', change, spark, note }) {
  return (
    <Box sx={{ p: 1.9, display: 'flex', flexDirection: 'column', gap: 0.9, minWidth: 0 }}>
      <Label>{label}</Label>
      <Typography
        sx={{ fontSize: 27, lineHeight: 1.05, fontWeight: 660, letterSpacing: '-.03em', fontVariantNumeric: 'tabular-nums' }}
      >
        {value}
      </Typography>
      <Stack direction="row" alignItems="center" justifyContent="space-between" gap={1} sx={{ mt: 0.25 }}>
        {change ? <Pill tone={tone} dot>{change}</Pill> : <Box component="span" sx={{ fontSize: 11.5, color: 'text.secondary' }}>{note}</Box>}
        {spark?.length > 1 && <Sparkline points={spark} />}
      </Stack>
    </Box>
  )
}

/* ------------------------------------------------------------------ *
 * Funnel — each stage against the widest stage, plus its own conversion.
 * ------------------------------------------------------------------ */
export function Funnel({ stages = [] }) {
  const { palette } = useTheme()
  const top = Math.max(...stages.map((s) => s.value || 0), 1)

  return (
    <Stack gap={1.25}>
      {stages.map((s) => (
        <Box
          key={s.label}
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: '92px 1fr', sm: '112px 1fr 108px' },
            alignItems: 'center',
            gap: 1.25,
          }}
        >
          <Typography sx={{ fontSize: 12, color: 'text.secondary', fontWeight: 540 }}>{s.label}</Typography>
          <Box sx={{ height: 22, background: palette.t.panel2, borderRadius: '5px', overflow: 'hidden' }}>
            <Box
              sx={{
                height: '100%',
                width: `${Math.max(1.5, ((s.value || 0) / top) * 100)}%`,
                borderRadius: '5px',
                background: palette.t.accent,
                opacity: s.dim ? 0.34 : 0.9,
                transition: 'width .45s cubic-bezier(.2,.7,.3,1)',
              }}
            />
          </Box>
          <Box sx={{ textAlign: 'right', fontSize: 12, fontVariantNumeric: 'tabular-nums', fontWeight: 600, display: { xs: 'none', sm: 'block' } }}>
            {fmt.number(s.value)}
            {s.rate != null && (
              <Box component="em" sx={{ fontStyle: 'normal', color: palette.t.faint, fontWeight: 500, fontSize: 11, ml: 0.75 }}>
                {fmt.pct(s.rate)}
              </Box>
            )}
          </Box>
        </Box>
      ))}
    </Stack>
  )
}

/* ------------------------------------------------------------------ *
 * EmptyState — says what is missing and what to do about it.
 * ------------------------------------------------------------------ */
export function EmptyState({ title, body, action }) {
  const { palette } = useTheme()
  return (
    <Stack alignItems="center" gap={1} sx={{ py: 6, px: 3, textAlign: 'center' }}>
      <Typography variant="h6">{title}</Typography>
      <Typography variant="body2" sx={{ color: palette.t.muted, maxWidth: '46ch' }}>{body}</Typography>
      {action && <Box sx={{ mt: 1 }}>{action}</Box>}
    </Stack>
  )
}

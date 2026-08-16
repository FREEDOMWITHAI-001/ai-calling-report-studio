import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Alert, Box, Button, LinearProgress, Stack, Table, TableBody, TableCell, TableHead, TableRow,
  Typography, useTheme,
} from '@mui/material'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import { Delta, EmptyState, Funnel, HGrid, Label, Panel, Pill, StatTile } from '../components/ui/index.jsx'
import { useApp } from '../state/AppState.jsx'
import { api, fmt } from '../api.js'

/** Cumulative daily series for a headline, used only for tile sparklines. */
function series(daily, pick) {
  if (!daily?.length) return []
  let running = 0
  return daily.map((d) => {
    running += (d.rows || []).reduce((sum, r) => sum + (pick(r) || 0), 0)
    return running
  })
}

export default function Overview() {
  const { palette } = useTheme()
  const { clientId, range, ready, bootError } = useApp()
  const [metrics, setMetrics] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!ready || !clientId || !range?.from || !range?.to) return
    let alive = true
    setLoading(true)
    setError(null)
    api.previewReport({ client_id: clientId, date_from: range.from, date_to: range.to })
      .then((m) => { if (alive) setMetrics(m) })
      .catch((e) => { if (alive) { setError(e.message); setMetrics(null) } })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [clientId, range?.from, range?.to, ready])

  const h = metrics?.headline
  const calls = metrics?.calls
  const sig = metrics?.significance

  const sparks = useMemo(() => ({
    buyers: series(metrics?.daily, (r) => (r.key === 'total' ? r.buyers : 0)),
    showed: series(metrics?.daily, (r) => (r.key === 'total' ? r.showed : 0)),
    regs: series(metrics?.daily, (r) => (r.key === 'total' ? r.registrants : 0)),
  }), [metrics])

  const stages = h && calls ? [
    { label: 'Registered', value: h.registrants },
    { label: 'Calls placed', value: calls.calls_placed },
    { label: 'Connected', value: h.connected_people, rate: h.registrants ? h.connected_people / h.registrants : null },
    { label: 'Showed up', value: h.showed, rate: h.registrants ? h.showed / h.registrants : null, dim: true },
    { label: 'Bought', value: h.buyers, rate: h.registrants ? h.buyers / h.registrants : null, dim: true },
  ] : []

  /* by_bot is keyed by bot name -> { calls, cost, role, … } */
  const botRows = useMemo(() => {
    const byBot = calls?.by_bot || {}
    return Object.entries(byBot)
      .map(([name, v]) => ({ name, calls: v.calls || 0, cost: v.cost || 0, role: v.role || 'other' }))
      .sort((a, b) => b.cost - a.cost)
      .slice(0, 8)
  }, [calls])

  /* groups is an object keyed by segment; total reads best at the bottom */
  const groupRows = useMemo(() => {
    const g = metrics?.groups || {}
    const rows = Object.entries(g).map(([key, v]) => ({ key, ...v }))
    return [...rows.filter((r) => r.key !== 'total'), ...rows.filter((r) => r.key === 'total')]
  }, [metrics])

  if (bootError) return <Alert severity="error">{bootError}</Alert>

  return (
    <Stack gap={2.25}>
      <Stack direction="row" alignItems="flex-end" gap={1.5} flexWrap="wrap">
        <Box>
          <Typography variant="h4">Overview</Typography>
          <Typography variant="body2" sx={{ color: palette.t.muted }}>
            {metrics?.meta
              ? `${metrics.meta.window_days} days · ${fmt.date(metrics.meta.date_from)} – ${fmt.date(metrics.meta.date_to)}`
              : 'Pick a client and a date range.'}
          </Typography>
        </Box>
        <Box sx={{ flex: 1 }} />
        <Button variant="outlined" component={Link} to="/ingest">Upload data</Button>
        <Button variant="contained" startIcon={<AddRoundedIcon />} component={Link} to="/reports?new=1">
          Generate report
        </Button>
      </Stack>

      {loading && <LinearProgress />}
      {error && <Alert severity="error">{error}</Alert>}

      {!loading && !error && h && !h.registrants && (
        <Panel>
          <EmptyState
            title="No registrants in this window"
            body="Nothing was registered between these dates for this client. Widen the range, switch client, or upload the data first."
            action={<Button variant="contained" component={Link} to="/ingest">Upload data</Button>}
          />
        </Panel>
      )}

      {h && !!h.registrants && (
        <>
          <HGrid columns={{ xs: '1fr 1fr', md: 'repeat(4, 1fr)' }}>
            <StatTile
              label="Return on talk cost"
              value={fmt.multiple(h.roi)}
              tone={h.roi >= 1 ? 'pos' : 'crit'}
              change={h.talk_cost ? `${fmt.money(h.talk_cost)} spent` : 'no cost data'}
            />
            <StatTile
              label="Revenue added"
              value={fmt.money(h.revenue_added)}
              tone={h.relative_uplift >= 0 ? 'pos' : 'crit'}
              change={h.relative_uplift != null ? `${fmt.delta(h.relative_uplift)} vs baseline` : null}
              note={`of ${fmt.money(h.revenue_with_ai)} total`}
              spark={sparks.buyers}
            />
            <StatTile
              label="Buyers"
              value={fmt.number(h.buyers)}
              tone="accent"
              change={h.extra_sales != null ? `${h.extra_sales >= 0 ? '+' : ''}${h.extra_sales.toFixed(1)} attributable` : null}
              spark={sparks.buyers}
            />
            <StatTile
              label="Connected leads"
              value={fmt.number(h.connected_people)}
              tone={sig?.buying?.significant ? 'pos' : 'neutral'}
              change={sig?.buying?.significant ? 'uplift significant' : 'not yet significant'}
              spark={sparks.regs}
            />
          </HGrid>

          <Box sx={{ display: 'grid', gap: 2, gridTemplateColumns: { xs: '1fr', lg: '1.35fr 1fr' } }}>
            <Panel
              title="Funnel"
              action={<Pill>{fmt.number(h.registrants)} registrants</Pill>}
            >
              <Funnel stages={stages} />
            </Panel>

            <Panel
              title="Bots in this window"
              flush
              action={<Pill>{Object.keys(calls?.by_bot || {}).length} active</Pill>}
            >
              {botRows.length ? (
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Bot</TableCell><TableCell>Role</TableCell>
                      <TableCell align="right">Calls</TableCell><TableCell align="right">Talk cost</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {botRows.map((b) => (
                      <TableRow key={b.name}>
                        <TableCell sx={{ maxWidth: 190, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={b.name}>{b.name}</TableCell>
                        <TableCell>
                          <Pill tone={b.role === 'signup' ? 'accent' : b.role === 'day_of' ? 'pos' : 'neutral'}>{b.role}</Pill>
                        </TableCell>
                        <TableCell align="right" sx={{ fontVariantNumeric: 'tabular-nums' }}>{fmt.number(b.calls)}</TableCell>
                        <TableCell align="right" sx={{ fontVariantNumeric: 'tabular-nums' }}>{fmt.money(b.cost)}</TableCell>
                      </TableRow>
                    ))}
                    <TableRow sx={{ '& td': { fontWeight: 660, background: palette.t.panel2 } }}>
                      <TableCell colSpan={2}>All bots</TableCell>
                      <TableCell align="right" sx={{ fontVariantNumeric: 'tabular-nums' }}>{fmt.number(calls?.calls_placed)}</TableCell>
                      <TableCell align="right" sx={{ fontVariantNumeric: 'tabular-nums' }}>{fmt.money(calls?.talk_cost)}</TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              ) : (
                <EmptyState title="No calls in this window" body="No AI call rows fall inside these dates for this client." />
              )}
            </Panel>
          </Box>

          <Panel
            title="Uplift by segment"
            flush
            action={
              <Stack direction="row" gap={0.75} flexWrap="wrap">
                {sig?.show_up && <Pill tone={sig.show_up.significant ? 'pos' : 'neutral'} dot>show-up p={sig.show_up.p_value?.toFixed(3)}</Pill>}
                {sig?.buying && <Pill tone={sig.buying.significant ? 'pos' : 'neutral'} dot>buying p={sig.buying.p_value?.toFixed(3)}</Pill>}
              </Stack>
            }
          >
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Segment</TableCell>
                  <TableCell align="right">Registrants</TableCell>
                  <TableCell align="right">Showed</TableCell>
                  <TableCell align="right">Show-up&nbsp;%</TableCell>
                  <TableCell align="right">Δ</TableCell>
                  <TableCell align="right">Buyers</TableCell>
                  <TableCell align="right">Buyer&nbsp;%</TableCell>
                  <TableCell align="right">Δ</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {groupRows.map((row, i) => {
                  const total = row.key === 'total'
                  const baseline = row.key === 'baseline'
                  return (
                    <TableRow
                      key={`${row.key}-${i}`}
                      sx={{
                        '& td': {
                          fontWeight: total ? 660 : 400,
                          background: total ? palette.t.panel2 : baseline ? palette.t.warnSoft : 'transparent',
                          fontVariantNumeric: 'tabular-nums',
                        },
                      }}
                    >
                      <TableCell sx={{ fontVariantNumeric: 'normal !important' }}>{row.label}</TableCell>
                      <TableCell align="right">{fmt.number(row.registrants)}</TableCell>
                      <TableCell align="right">{fmt.number(row.showed)}</TableCell>
                      <TableCell align="right">{fmt.pct(row.show_rate)}</TableCell>
                      <TableCell align="right"><Delta value={row.show_delta} /></TableCell>
                      <TableCell align="right">{fmt.number(row.buyers)}</TableCell>
                      <TableCell align="right">{fmt.pct(row.buy_rate, 2)}</TableCell>
                      <TableCell align="right"><Delta value={row.buy_delta} decimals={2} /></TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </Panel>

          <HGrid columns={{ xs: '1fr 1fr', md: 'repeat(4, 1fr)' }}>
            {[
              ['Calls placed', fmt.number(calls?.calls_placed)],
              ['Talk minutes', fmt.number(calls?.talk_minutes_exact, 1)],
              ['Match rate', fmt.pct(calls?.match_rate)],
              ['Breakeven sales', calls && h.breakeven_sales != null ? h.breakeven_sales.toFixed(2) : '—'],
            ].map(([label, value]) => (
              <Box key={label} sx={{ p: 1.9, display: 'flex', flexDirection: 'column', gap: 0.6 }}>
                <Label>{label}</Label>
                <Typography sx={{ fontSize: 19, fontWeight: 640, letterSpacing: '-.02em', fontVariantNumeric: 'tabular-nums' }}>
                  {value}
                </Typography>
              </Box>
            ))}
          </HGrid>
        </>
      )}
    </Stack>
  )
}

import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  Accordion, AccordionDetails, AccordionSummary, Alert, Box, Button, Card, CardContent,
  Checkbox, Chip, CircularProgress, Divider, FormControl, FormControlLabel, Grid, IconButton,
  InputLabel, LinearProgress, MenuItem, Paper, Select, Stack, Table, TableBody, TableCell,
  TableHead, TableRow, TextField, Tooltip, Typography, useTheme,
} from '@mui/material'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import DownloadIcon from '@mui/icons-material/Download'
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline'
import RefreshIcon from '@mui/icons-material/Refresh'
import {
  Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip as ReTooltip, XAxis, YAxis,
} from 'recharts'
import MetricCard from '../components/MetricCard.jsx'
import GroupTable from '../components/GroupTable.jsx'
import { api, fmt } from '../api.js'
import { useApp } from '../state/AppState.jsx'

const FORMATS = [
  { key: 'pdf', label: 'PDF' },
  { key: 'xlsx', label: 'Excel' },
  { key: 'pptx', label: 'PowerPoint' },
]

/** A z-test returns null when a group is empty — say so instead of crashing. */
function fmtP(test) {
  if (!test || test.p_value === null || test.p_value === undefined) return 'n/a'
  return `p = ${test.p_value.toFixed(4)}`
}

export default function ReportsPage() {
  const { palette } = useTheme()
  const { clientId, client } = useApp()
  const [summary, setSummary] = useState(null)
  const [bots, setBots] = useState([])
  const [presets, setPresets] = useState([])
  const [methodologies, setMethodologies] = useState([])
  const [reportFormats, setReportFormats] = useState([])
  const [form, setForm] = useState({
    title: '', date_from: '', date_to: '', language: '', product: '',
    bot_names: [], formats: ['pdf', 'xlsx', 'pptx'], methodology_id: '',
    template: '',            // '' = this client's default format
    use_template: true,      // false = the original webinar-uplift report
  })
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState(null)
  const [runs, setRuns] = useState([])

  useEffect(() => {
    if (!clientId) return
    // Reset per-client state so one org's runs never linger on another's page.
    setResult(null)
    setRuns([])
    Promise.all([api.summary(), api.bots(), api.presets(), api.methodologies(),
      api.reports(), api.formats()])
      .then(([sum, botList, presetList, methods, runList, formatList]) => {
        setSummary(sum)
        setBots(botList)
        setPresets(presetList)
        setMethodologies(methods)
        setRuns(runList)
        setReportFormats(formatList)
        const reg = sum.tables?.registrations
        setForm((prev) => ({
          ...prev,
          date_from: reg?.min_date || '',
          date_to: reg?.max_date || '',
          language: sum.languages?.[0] ?? '',
          bot_names: [],
          template: '',
          use_template: true,
        }))
      })
      .catch((e) => setError(e.message))
  }, [clientId])

  const refreshRuns = () => api.reports().then(setRuns).catch(() => {})

  useEffect(() => {
    if (!runs.some((r) => ['queued', 'running'].includes(r.status))) return undefined
    const timer = setInterval(refreshRuns, 2000)
    return () => clearInterval(timer)
  }, [runs])

  const body = useMemo(() => ({
    title: form.title || undefined,
    date_from: form.date_from,
    date_to: form.date_to,
    language: form.language || undefined,
    product: form.product || undefined,
    bot_names: form.bot_names.length ? form.bot_names : undefined,
    formats: form.formats,
    methodology_id: form.methodology_id || undefined,
    // Blank template means "this client's default format".
    template: form.template || undefined,
    use_template: form.use_template,
  }), [form])

  const activeFormat = form.use_template
    ? (reportFormats.find((f) => f.key === form.template)
       || reportFormats.find((f) => f.is_default))
    : null

  const runPreview = async () => {
    setBusy(true); setError(null)
    try {
      setResult(await api.previewReport(body))
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  const generate = async () => {
    setGenerating(true); setError(null)
    try {
      await api.createReport(body)
      await refreshRuns()
    } catch (e) { setError(e.message) } finally { setGenerating(false) }
  }

  const applyPreset = (preset) =>
    setForm((prev) => ({ ...prev, date_from: preset.date_from, date_to: preset.date_to }))

  const toggleFormat = (key) =>
    setForm((prev) => ({
      ...prev,
      formats: prev.formats.includes(key)
        ? prev.formats.filter((f) => f !== key)
        : [...prev.formats, key],
    }))

  const head = result?.headline
  const dailyChart = (result?.daily || []).map((day) => {
    const rows = Object.fromEntries(day.rows.map((r) => [r.key, r]))
    const both = rows.both?.registrants || 0
    const connected = (rows.signup?.registrants || 0) + (rows.day_of?.registrants || 0) - both
    return {
      date: fmt.date(day.date).replace(/ \d{4}$/, ''),
      Connected: connected,
      Baseline: rows.baseline?.registrants || 0,
    }
  })

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4">Generate a report</Typography>
        <Typography variant="body2" color="text.secondary">
          Pick a window, preview the numbers, then export PDF / Excel / PowerPoint in one action.
        </Typography>
      </Box>

      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}

      <Card>
        <CardContent>
          <Grid container spacing={2} alignItems="center">
            <Grid item xs={12} md={2}>
              <TextField label="From" type="date" fullWidth size="small" InputLabelProps={{ shrink: true }}
                value={form.date_from} onChange={(e) => setForm({ ...form, date_from: e.target.value })} />
            </Grid>
            <Grid item xs={12} md={2}>
              <TextField label="To" type="date" fullWidth size="small" InputLabelProps={{ shrink: true }}
                value={form.date_to} onChange={(e) => setForm({ ...form, date_to: e.target.value })} />
            </Grid>
            <Grid item xs={12} md={2}>
              <FormControl fullWidth size="small">
                <InputLabel>Language / segment</InputLabel>
                <Select label="Language / segment" value={form.language}
                  onChange={(e) => setForm({ ...form, language: e.target.value })}>
                  <MenuItem value="">All</MenuItem>
                  {(summary?.languages || []).map((l) => <MenuItem key={l} value={l}>{l}</MenuItem>)}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={3}>
              <FormControl fullWidth size="small">
                <InputLabel>Bots (blank = signup + day-of)</InputLabel>
                <Select multiple label="Bots (blank = signup + day-of)" value={form.bot_names}
                  onChange={(e) => setForm({ ...form, bot_names: e.target.value })}
                  renderValue={(selected) => `${selected.length} selected`}>
                  {bots.map((bot) => (
                    <MenuItem key={bot.id} value={bot.name}>
                      <Checkbox size="small" checked={form.bot_names.includes(bot.name)} />
                      {bot.name} <Chip size="small" sx={{ ml: 1 }} label={bot.role} />
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Grid>
            <Grid item xs={12} md={3}>
              <TextField label="Report title (optional)" fullWidth size="small" value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="CBA X · English" />
            </Grid>

            <Grid item xs={12}>
              <Stack
                direction="row" spacing={1.5} alignItems="center" flexWrap="wrap" useFlexGap
                sx={{
                  p: 1.5, borderRadius: '10px', border: `1px solid ${palette.t.border}`,
                  background: palette.t.panel2,
                }}
              >
                <FormControl size="small" sx={{ minWidth: 260 }}>
                  <InputLabel>Report format</InputLabel>
                  <Select
                    label="Report format"
                    value={form.use_template ? form.template : '__legacy__'}
                    onChange={(e) => {
                      const value = e.target.value
                      setForm({
                        ...form,
                        use_template: value !== '__legacy__',
                        template: value === '__legacy__' ? '' : value,
                      })
                    }}
                  >
                    <MenuItem value="">
                      {client?.name || 'Client'} default
                      {reportFormats.find((f) => f.is_default)
                        ? ` — ${reportFormats.find((f) => f.is_default).name}`
                        : ''}
                    </MenuItem>
                    {reportFormats.filter((f) => f.source === 'client').map((f) => (
                      <MenuItem key={f.key} value={f.key}>{f.name}</MenuItem>
                    ))}
                    <Divider />
                    {reportFormats.filter((f) => f.source === 'built-in').map((f) => (
                      <MenuItem key={f.key} value={f.key}>{f.name} (built-in)</MenuItem>
                    ))}
                    <Divider />
                    <MenuItem value="__legacy__">Original webinar-uplift report</MenuItem>
                  </Select>
                </FormControl>

                {activeFormat ? (
                  <Stack direction="row" spacing={0.75} alignItems="center" flexWrap="wrap" useFlexGap>
                    <Chip size="small" label={`${activeFormat.sections.length} sections`} />
                    <Chip size="small" variant="outlined" label={`→ ${activeFormat.formats.join(', ')}`} />
                    <Typography variant="caption" color="text.secondary">
                      {activeFormat.sections.slice(0, 6).map((s) => s.title || s.key).join(' · ')}
                      {activeFormat.sections.length > 6 ? ' …' : ''}
                    </Typography>
                  </Stack>
                ) : (
                  <Typography variant="caption" color="text.secondary">
                    The original single-sheet report — PDF, Excel and PowerPoint.
                  </Typography>
                )}
                <Box sx={{ flexGrow: 1 }} />
                <Button size="small" component={Link} to="/formats">Manage formats</Button>
              </Stack>
            </Grid>

            <Grid item xs={12}>
              <Stack direction="row" spacing={1} flexWrap="wrap" alignItems="center" useFlexGap>
                {presets.map((preset) => (
                  <Chip key={preset.key} label={preset.label} variant="outlined" onClick={() => applyPreset(preset)} />
                ))}
                <Divider orientation="vertical" flexItem sx={{ mx: 1 }} />
                {FORMATS.map((f) => (
                  <FormControlLabel key={f.key} control={
                    <Checkbox size="small" checked={form.formats.includes(f.key)} onChange={() => toggleFormat(f.key)} />
                  } label={f.label} />
                ))}
                {methodologies.length > 0 && (
                  <FormControl size="small" sx={{ minWidth: 200 }}>
                    <InputLabel>Methodology</InputLabel>
                    <Select label="Methodology" value={form.methodology_id}
                      onChange={(e) => setForm({ ...form, methodology_id: e.target.value })}>
                      <MenuItem value="">Default</MenuItem>
                      {methodologies.map((m) => <MenuItem key={m.id} value={m.id}>{m.name}</MenuItem>)}
                    </Select>
                  </FormControl>
                )}
                <Box sx={{ flexGrow: 1 }} />
                <Button variant="outlined" onClick={runPreview} disabled={busy || !form.date_from}>
                  {busy ? 'Computing…' : 'Preview numbers'}
                </Button>
                <Button variant="contained" onClick={generate}
                  disabled={generating || !form.date_from || !form.formats.length}>
                  {generating ? 'Queued…' : `Generate ${form.formats.length} file(s)`}
                </Button>
              </Stack>
            </Grid>
          </Grid>
          {busy && <LinearProgress sx={{ mt: 2 }} />}
        </CardContent>
      </Card>

      {head && (
        <>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6} md={3}>
              <MetricCard label="Revenue with AI" value={fmt.money(head.revenue_with_ai)}
                sub={`${fmt.number(head.buyers)} buyers × ${fmt.money(head.sale_value)}`} />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <MetricCard label="Revenue without AI" value={fmt.money(head.revenue_without_ai)} sub="counterfactual" />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <MetricCard label="AI calling added" value={fmt.money(head.revenue_added)}
                sub={`${head.extra_sales?.toFixed(1) ?? '—'} extra sales · ${fmt.pct(head.relative_uplift)} uplift`} />
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <MetricCard accent label="ROI" value={fmt.multiple(head.roi)}
                sub={`talk cost ${fmt.money(head.talk_cost)} · break-even ${head.breakeven_sales?.toFixed(1)} sales`} />
            </Grid>
          </Grid>

          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>Show-up &amp; buyers by bot reached</Typography>
              <Typography variant="caption" color="text.secondary">
                Δ compares each group with the baseline ({result.groups?.baseline?.label || 'not connected'}). Bot rows
                overlap: a lead reached by both appears in each.
              </Typography>
              <Box sx={{ mt: 2, overflowX: 'auto' }}>
                <GroupTable rows={['total', 'signup', 'day_of', 'both', 'baseline']
                  .filter((key) => result.groups?.[key])
                  .map((key) => ({ ...result.groups[key], key }))} />
              </Box>
              <Alert severity="info" sx={{ mt: 2 }}>
                Show-up {fmtP(result.significance?.show_up)} · Buying {fmtP(result.significance?.buying)}
                {' '}(two-proportion z-test vs baseline). Observational comparison — connected leads are self-selected.
              </Alert>
            </CardContent>
          </Card>

          <Grid container spacing={2}>
            <Grid item xs={12} md={7}>
              <Card sx={{ height: '100%' }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>Registrants per day</Typography>
                  <Box sx={{ height: 300 }}>
                    <ResponsiveContainer>
                      <BarChart data={dailyChart}>
                        <CartesianGrid strokeDasharray="3 3" stroke={palette.t.border} />
                        <XAxis dataKey="date" fontSize={11} stroke={palette.t.faint} />
                        <YAxis fontSize={11} stroke={palette.t.faint} />
                        <ReTooltip
                          contentStyle={{
                            background: palette.t.panel,
                            border: `1px solid ${palette.t.border}`,
                            borderRadius: 8,
                            fontSize: 12,
                            color: palette.t.text,
                          }}
                          cursor={{ fill: palette.t.panel2 }}
                        />
                        <Legend wrapperStyle={{ fontSize: 12, color: palette.t.muted }} />
                        <Bar dataKey="Connected" stackId="a" fill={palette.t.accent} />
                        <Bar dataKey="Baseline" stackId="a" fill={palette.t.borderStrong} />
                      </BarChart>
                    </ResponsiveContainer>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={5}>
              <Card sx={{ height: '100%' }}>
                <CardContent>
                  <Typography variant="h6" gutterBottom>Extra sales, weighted by lead age</Typography>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Band</TableCell>
                        <TableCell align="right">Connected</TableCell>
                        <TableCell align="right">Buy %</TableCell>
                        <TableCell align="right">Baseline buy %</TableCell>
                        <TableCell align="right">Extra</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {(result.bands || []).map((band) => (
                        <TableRow key={band.band}>
                          <TableCell>{band.band}</TableCell>
                          <TableCell align="right">{fmt.number(band.connected)}</TableCell>
                          <TableCell align="right">{fmt.pct(band.connected_buy_rate, 2)}</TableCell>
                          <TableCell align="right">{fmt.pct(band.baseline_buy_rate, 2)}</TableCell>
                          <TableCell align="right">{band.extra_sales?.toFixed(1) ?? '—'}</TableCell>
                        </TableRow>
                      ))}
                      <TableRow sx={{ '& td': { fontWeight: 700 } }}>
                        <TableCell colSpan={4}>Total credited to AI</TableCell>
                        <TableCell align="right">{head.extra_sales?.toFixed(1) ?? '—'}</TableCell>
                      </TableRow>
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </Grid>
          </Grid>

          <Accordion>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="subtitle1">Per-call-day detail ({(result.daily || []).length} days)</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Stack spacing={3}>
                {(result.daily || []).map((day) => (
                  <Box key={day.date}>
                    <Typography variant="subtitle2" color="primary" gutterBottom>{fmt.date(day.date)}</Typography>
                    <GroupTable rows={day.rows} dense />
                  </Box>
                ))}
              </Stack>
            </AccordionDetails>
          </Accordion>

          <Accordion>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="subtitle1">Method, sources &amp; data audit</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Grid container spacing={2}>
                {Object.entries(result.audit || {}).map(([key, value]) => (
                  <Grid item xs={6} md={3} key={key}>
                    <Typography variant="caption" color="text.secondary">{key.replace(/_/g, ' ')}</Typography>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {typeof value === 'number' ? fmt.number(value, Number.isInteger(value) ? 0 : 2) : String(value ?? '—')}
                    </Typography>
                  </Grid>
                ))}
                {Object.entries(result.calls || {}).filter(([, v]) => typeof v !== 'object').map(([key, value]) => (
                  <Grid item xs={6} md={3} key={key}>
                    <Typography variant="caption" color="text.secondary">calls · {key.replace(/_/g, ' ')}</Typography>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                      {typeof value === 'number' ? fmt.number(value, Number.isInteger(value) ? 0 : 2) : String(value ?? '—')}
                    </Typography>
                  </Grid>
                ))}
              </Grid>
            </AccordionDetails>
          </Accordion>
        </>
      )}

      <Card>
        <CardContent>
          <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
            <Typography variant="h6">Report history</Typography>
            <IconButton size="small" onClick={refreshRuns}><RefreshIcon fontSize="small" /></IconButton>
          </Stack>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Title</TableCell>
                <TableCell>Format</TableCell>
                <TableCell>Window</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Generated</TableCell>
                <TableCell align="right">Downloads</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {runs.map((run) => (
                <TableRow key={run.id}>
                  <TableCell>{run.title}</TableCell>
                  <TableCell>
                    {run.template_label
                      ? <Chip size="small" variant="outlined" label={run.template_label} />
                      : <Typography variant="caption" color="text.secondary">unrecorded</Typography>}
                  </TableCell>
                  <TableCell>{fmt.date(run.date_from)} – {fmt.date(run.date_to)}</TableCell>
                  <TableCell>
                    {['queued', 'running'].includes(run.status)
                      ? <Stack direction="row" spacing={1} alignItems="center"><CircularProgress size={14} /><span>{run.status}</span></Stack>
                      : <Chip size="small" color={run.status === 'success' ? 'success' : 'error'} label={run.status} />}
                    {run.error_detail && (
                      <Tooltip title={run.error_detail}><Chip size="small" color="error" sx={{ ml: 1 }} label="details" /></Tooltip>
                    )}
                  </TableCell>
                  <TableCell>{fmt.dateTime(run.generated_at)}</TableCell>
                  <TableCell align="right">
                    <Stack direction="row" spacing={1} justifyContent="flex-end">
                      {(run.files || []).map((file) => (
                        <Button key={file.format} size="small" startIcon={<DownloadIcon />}
                          href={api.downloadUrl(run.id, file.format)}>
                          {file.format.toUpperCase()}
                        </Button>
                      ))}
                      <IconButton size="small" onClick={() => api.deleteReport(run.id).then(refreshRuns)}>
                        <DeleteOutlineIcon fontSize="small" />
                      </IconButton>
                    </Stack>
                  </TableCell>
                </TableRow>
              ))}
              {!runs.length && (
                <TableRow><TableCell colSpan={6}>
                  <Typography variant="body2" color="text.secondary">No reports generated yet.</Typography>
                </TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </Stack>
  )
}

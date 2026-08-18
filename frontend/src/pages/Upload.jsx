import { useEffect, useRef, useState } from 'react'
import {
  Alert, Box, Button, Card, CardContent, Chip, FormControl, Grid, IconButton, InputLabel,
  LinearProgress, MenuItem, Paper, Select, Stack, Step, StepLabel, Stepper, Table, TableBody,
  TableCell, TableHead, TableRow, TextField, Tooltip, Typography,
} from '@mui/material'
import UploadFileIcon from '@mui/icons-material/UploadFile'
import TuneIcon from '@mui/icons-material/Tune'
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline'
import { api, fmt } from '../api.js'
import { useApp } from '../state/AppState.jsx'
import { Pill } from '../components/ui/index.jsx'

const STEPS = ['Choose file', 'Pick sheet', 'Map columns', 'Load']

export default function UploadPage() {
  // The upload target is the client selected in the top bar — never typed in
  // here. A free-text client field is how files ended up in the wrong org.
  const { client, clientId } = useApp()
  const fileRef = useRef(null)
  const [datasets, setDatasets] = useState([])
  const [uploads, setUploads] = useState([])
  const [upload, setUpload] = useState(null)
  const [sheet, setSheet] = useState('')
  const [preview, setPreview] = useState(null)
  const [datasetType, setDatasetType] = useState('custom')
  const [mapping, setMapping] = useState({})
  const [options, setOptions] = useState({ language: '', program: '', product: '' })
  const [busy, setBusy] = useState(false)
  const [progress, setProgress] = useState(null)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)

  const step = !upload ? 0 : !preview ? 1 : busy ? 3 : 2

  const refresh = () => api.uploads().then(setUploads).catch(() => {})

  useEffect(() => {
    api.datasets().then(setDatasets).catch((e) => setError(e.message))
  }, [])

  // Switching client resets the in-progress upload: a file picked for one org
  // must never be ingested into another.
  useEffect(() => {
    setUpload(null); setPreview(null); setUploads([])
    if (clientId) refresh()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientId])

  useEffect(() => {
    if (!uploads.some((u) => ['queued', 'processing'].includes(u.status))) return undefined
    const timer = setInterval(refresh, 2000)
    return () => clearInterval(timer)
  }, [uploads])

  const onFile = async (event) => {
    const file = event.target.files?.[0]
    if (!file) return
    setBusy(true); setError(null); setPreview(null); setUpload(null); setProgress(0)
    try {
      const created = await api.upload(file, setProgress)
      setUpload(created)
      const first = created.sheets?.[0]?.name || ''
      setSheet(created.is_excel ? first : '')
      await loadPreview(created.id, created.is_excel ? first : undefined)
    } catch (e) { setError(e.message) } finally { setBusy(false); setProgress(null) }
  }

  const loadPreview = async (id, sheetName, forceType) => {
    setBusy(true)
    try {
      const data = await api.preview(id, sheetName)
      setPreview(data)
      // Re-opening keeps the type it was loaded as; a fresh file takes the
      // detected one.
      const type = forceType || data.suggested_type
      setDatasetType(type)
      setMapping((forceType && data.mapping_options?.[forceType]) || data.suggested_mapping || {})
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  const changeType = (type) => {
    setDatasetType(type)
    setMapping(preview?.mapping_options?.[type] || {})
  }

  const ingest = async () => {
    setBusy(true); setError(null)
    try {
      await api.ingest(upload.id, {
        dataset_type: datasetType,
        sheet: sheet || null,
        mapping,
        language: options.language || null,
        program: options.program || null,
        product: options.product || null,
        generic_dataset_name: datasetType === 'custom' ? (sheet || upload.filename) : null,
      })
      setNotice(`Loading "${upload.filename}" into ${datasetType} for ${client?.name} — watch the log below.`)
      setUpload(null); setPreview(null)
      refresh()
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  // Reopen an already-loaded file at the mapping step. Used when the detected
  // type was wrong: re-running the ingest replaces the rows it created the
  // first time, so the correction leaves no trace of the mistake behind.
  const reclassify = async (row) => {
    setError(null); setNotice(null)
    setUpload({ id: row.id, filename: row.filename, size_bytes: row.size_bytes, sheets: [], is_excel: false })
    setSheet(row.sheet_name || '')
    // Restore what this file was loaded with, so re-running it keeps the
    // language and programme unless they are deliberately changed.
    const prev = row.options || {}
    setOptions({
      language: prev.language || '',
      program: prev.program || '',
      product: prev.product || '',
    })
    await loadPreview(row.id, row.sheet_name || undefined, row.dataset_type)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const remove = async (row) => {
    const n = fmt.number(row.inserted_count || 0)
    if (!window.confirm(`Delete "${row.filename}" and the ${n} rows it loaded into ${row.dataset_type || 'the database'}?

This cannot be undone.`)) return
    setBusy(true); setError(null); setNotice(null)
    try {
      const res = await api.deleteUpload(row.id)
      const detail = Object.entries(res?.rows_removed || {})
        .map(([table, count]) => `${fmt.number(count)} ${table}`).join(', ')
      setNotice(`Deleted "${row.filename}"${detail ? ` and its rows (${detail})` : ''}.`)
      if (upload?.id === row.id) { setUpload(null); setPreview(null) }
      refresh()
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  const activeDataset = datasets.find((d) => d.key === datasetType)

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4">Ingest data</Typography>
        <Typography variant="body2" color="text.secondary">
          Any CSV or Excel file. The app guesses the data type and column mapping; you confirm or change it.
        </Typography>
      </Box>

      {/* Which org this file lands in — stated before anything is chosen, and
          not editable here. Change it with the client switcher in the top bar. */}
      <Alert
        severity={clientId ? 'info' : 'warning'}
        icon={false}
        sx={{ '& .MuiAlert-message': { width: '100%' } }}
      >
        <Stack direction="row" alignItems="center" gap={1.25} flexWrap="wrap">
          <Typography variant="body2" sx={{ fontWeight: 600 }}>
            {clientId ? 'Loading into' : 'No client selected'}
          </Typography>
          {clientId
            ? <Pill tone="accent" dot>{client?.name}</Pill>
            : <Typography variant="body2">Pick one in the top bar before uploading.</Typography>}
          <Box sx={{ flex: 1 }} />
          <Typography variant="caption">
            Every row from this file is written to this client only. Switch client in the top bar to change it.
          </Typography>
        </Stack>
      </Alert>

      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}
      {notice && <Alert severity="success" onClose={() => setNotice(null)}>{notice}</Alert>}

      <Stepper activeStep={step} sx={{ mb: 1 }}>
        {STEPS.map((label) => <Step key={label}><StepLabel>{label}</StepLabel></Step>)}
      </Stepper>

      <Card>
        <CardContent>
          <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap" useFlexGap>
            <Button
              variant="contained"
              startIcon={<UploadFileIcon />}
              disabled={!clientId}
              onClick={() => fileRef.current?.click()}
            >
              Choose CSV / XLSX
            </Button>
            <input ref={fileRef} type="file" hidden accept=".csv,.xlsx,.xlsm,.tsv,.txt" onChange={onFile} />
            {upload && <Chip label={`${upload.filename} · ${fmt.number((upload.size_bytes || 0) / 1024)} KB`} />}
            {upload?.sheets?.length > 1 && (
              <FormControl size="small" sx={{ minWidth: 280 }}>
                <InputLabel>Sheet</InputLabel>
                <Select label="Sheet" value={sheet} onChange={(e) => { setSheet(e.target.value); loadPreview(upload.id, e.target.value) }}>
                  {upload.sheets.map((s) => (
                    <MenuItem key={s.name} value={s.name}>{s.name} {s.rows ? `(${s.rows} rows)` : ''}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            )}
          </Stack>
          {busy && (progress === null
            ? <LinearProgress sx={{ mt: 2 }} />
            : (
              <Box sx={{ mt: 2 }}>
                <LinearProgress variant="determinate" value={Math.round(progress * 100)} />
                <Typography variant="caption" color="text.secondary">
                  Uploading… {Math.round(progress * 100)}%
                </Typography>
              </Box>
            ))}
        </CardContent>
      </Card>

      {preview && (
        <Card>
          <CardContent>
            <Grid container spacing={2} alignItems="center" sx={{ mb: 2 }}>
              <Grid item xs={12} md={3}>
                <FormControl fullWidth size="small">
                  <InputLabel>Data type → table</InputLabel>
                  <Select label="Data type → table" value={datasetType} onChange={(e) => changeType(e.target.value)}>
                    {datasets.map((d) => <MenuItem key={d.key} value={d.key}>{d.label} → {d.table}</MenuItem>)}
                  </Select>
                </FormControl>
              </Grid>
              <Grid item xs={12} md={2}>
                <TextField size="small" fullWidth label="Language / segment" placeholder="English"
                  value={options.language} onChange={(e) => setOptions({ ...options, language: e.target.value })} />
              </Grid>
              <Grid item xs={12} md={2}>
                <TextField size="small" fullWidth label="Program" placeholder="CBA X"
                  value={options.program} onChange={(e) => setOptions({ ...options, program: e.target.value })} />
              </Grid>
              <Grid item xs={12} md={3}>
                <Stack direction="row" spacing={1} alignItems="center">
                  <Chip size="small" color={preview.confidence > 0.7 ? 'success' : 'warning'}
                    label={`auto-detected ${Math.round(preview.confidence * 100)}%`} />
                  {preview.template_used && <Chip size="small" label={`template: ${preview.template_used}`} />}
                </Stack>
              </Grid>
            </Grid>

            <Typography variant="subtitle2" gutterBottom>Column mapping</Typography>
            <Grid container spacing={1.5}>
              {(activeDataset?.fields || []).map((field) => (
                <Grid item xs={12} sm={6} md={3} key={field.key}>
                  <FormControl fullWidth size="small">
                    <InputLabel>{field.label}{field.required ? ' *' : ''}</InputLabel>
                    <Select label={`${field.label}${field.required ? ' *' : ''}`} value={mapping[field.key] || ''}
                      onChange={(e) => setMapping({ ...mapping, [field.key]: e.target.value || null })}
                      error={field.required && !mapping[field.key]}>
                      <MenuItem value="">— not in this file —</MenuItem>
                      {preview.columns.map((col) => <MenuItem key={col} value={col}>{col}</MenuItem>)}
                    </Select>
                  </FormControl>
                </Grid>
              ))}
            </Grid>

            <Typography variant="subtitle2" sx={{ mt: 3, mb: 1 }}>
              Preview — first {preview.rows.length} rows
            </Typography>
            <Paper variant="outlined" sx={{ overflowX: 'auto' }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    {preview.columns.map((col) => (
                      <TableCell key={col} sx={{ whiteSpace: 'nowrap', fontWeight: 700 }}>{col}</TableCell>
                    ))}
                  </TableRow>
                </TableHead>
                <TableBody>
                  {preview.rows.map((row, index) => (
                    <TableRow key={index}>
                      {preview.columns.map((col) => (
                        <TableCell key={col} sx={{ whiteSpace: 'nowrap', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {String(row[col] ?? '')}
                        </TableCell>
                      ))}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Paper>

            <Stack direction="row" spacing={2} sx={{ mt: 2 }}>
              <Button variant="contained" onClick={ingest} disabled={busy}>Load into database</Button>
              <Button onClick={() => { setUpload(null); setPreview(null) }}>Cancel</Button>
            </Stack>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>Upload log</Typography>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>File</TableCell>
                <TableCell>Sheet</TableCell>
                <TableCell>Type</TableCell>
                <TableCell align="right">Rows</TableCell>
                <TableCell align="right">Inserted</TableCell>
                <TableCell align="right">Skipped</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>When</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {uploads.map((row) => (
                <TableRow key={row.id}>
                  <TableCell sx={{ maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis' }}>{row.filename}</TableCell>
                  <TableCell>{row.sheet_name || '—'}</TableCell>
                  <TableCell>{row.dataset_type || '—'}</TableCell>
                  <TableCell align="right">{fmt.number(row.row_count)}</TableCell>
                  <TableCell align="right">{fmt.number(row.inserted_count)}</TableCell>
                  <TableCell align="right">{fmt.number(row.skipped_count)}</TableCell>
                  <TableCell>
                    <Chip size="small" label={row.status}
                      color={row.status === 'success' ? 'success' : row.status === 'failed' ? 'error' : row.status === 'partial' ? 'warning' : 'default'} />
                  </TableCell>
                  <TableCell>{fmt.dateTime(row.uploaded_at)}</TableCell>
                  <TableCell align="right">
                    <Stack direction="row" spacing={0.5} justifyContent="flex-end">
                      <Tooltip title="Wrong type or mapping? Reopen and load it again — this replaces the rows it created.">
                        <span>
                          <IconButton size="small" disabled={busy} onClick={() => reclassify(row)}>
                            <TuneIcon fontSize="small" />
                          </IconButton>
                        </span>
                      </Tooltip>
                      <Tooltip title="Delete this file and every row it loaded">
                        <span>
                          <IconButton size="small" color="error" disabled={busy} onClick={() => remove(row)}>
                            <DeleteOutlineIcon fontSize="small" />
                          </IconButton>
                        </span>
                      </Tooltip>
                    </Stack>
                  </TableCell>
                </TableRow>
              ))}
              {!uploads.length && (
                <TableRow><TableCell colSpan={9}>
                  <Typography variant="body2" color="text.secondary">Nothing uploaded yet.</Typography>
                </TableCell></TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </Stack>
  )
}

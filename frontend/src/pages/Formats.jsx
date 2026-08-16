import { useEffect, useMemo, useState } from 'react'
import {
  Alert, Box, Button, Checkbox, Dialog, DialogActions, DialogContent, DialogTitle,
  IconButton, LinearProgress, MenuItem, Select, Stack, TextField, Tooltip, Typography, useTheme,
} from '@mui/material'
import AddRoundedIcon from '@mui/icons-material/AddRounded'
import StarRoundedIcon from '@mui/icons-material/StarRounded'
import StarBorderRoundedIcon from '@mui/icons-material/StarBorderRounded'
import DeleteOutlineRoundedIcon from '@mui/icons-material/DeleteOutlineRounded'
import ArrowUpwardRoundedIcon from '@mui/icons-material/ArrowUpwardRounded'
import ArrowDownwardRoundedIcon from '@mui/icons-material/ArrowDownwardRounded'
import { EmptyState, HGrid, Label, Panel, Pill } from '../components/ui/index.jsx'
import { useApp } from '../state/AppState.jsx'
import { api } from '../api.js'

/** What a missing input means, in the user's words rather than the schema's. */
const REQUIRE_LABEL = {
  registrations: 'registrations',
  ai_calls: 'AI calling data',
  sales: 'sales',
  attendance: 'Zoom attendance',
  leads: 'supplied lead list',
  sale_grading: 'transcript grading',
}

export default function FormatsPage() {
  const { palette } = useTheme()
  const { client, clientId } = useApp()

  const [formats, setFormats] = useState([])
  const [builtIn, setBuiltIn] = useState([])
  const [library, setLibrary] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [editing, setEditing] = useState(null)

  const load = () => {
    if (!clientId) return
    setLoading(true)
    Promise.all([api.formats(), api.builtInFormats(), api.sectionLibrary()])
      .then(([f, b, l]) => { setFormats(f); setBuiltIn(b); setLibrary(l) })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [clientId])

  const libraryByKey = useMemo(
    () => Object.fromEntries(library.map((s) => [s.key, s])), [library],
  )

  const own = formats.filter((f) => f.source === 'client')
  const stock = formats.filter((f) => f.source === 'built-in')

  const startNew = () => {
    const base = builtIn[0]
    setEditing({
      key: '', name: '', base_key: base?.key || 'webinar',
      description: '', is_default: !own.length,
      sections: (base?.sections || []).map((s) => ({ ...s })),
      isNew: true,
    })
  }

  const startEdit = (format) => setEditing({
    id: format.id,
    key: format.key,
    name: format.name,
    base_key: format.base_key,
    description: format.description || '',
    is_default: format.is_default,
    sections: format.sections.map((s) => ({ ...s })),
    isNew: format.source !== 'client',
  })

  const save = async () => {
    try {
      await api.saveFormat({
        key: editing.key.trim(),
        name: editing.name.trim(),
        base_key: editing.base_key,
        description: editing.description || null,
        is_default: editing.is_default,
        spec: { sections: editing.sections.map((s) => ({ key: s.key, title: s.title })) },
      })
      setNotice(`Saved "${editing.name}".`)
      setEditing(null)
      load()
    } catch (e) { setError(e.message) }
  }

  const setDefault = async (format) => {
    try {
      await api.makeFormatDefault(format.id)
      setNotice(`${format.name} is now the default for ${client?.name}.`)
      load()
    } catch (e) { setError(e.message) }
  }

  const remove = async (format) => {
    try {
      await api.deleteFormat(format.id)
      setNotice(`Deleted "${format.name}".`)
      load()
    } catch (e) { setError(e.message) }
  }

  const move = (index, delta) => {
    const next = [...editing.sections]
    const target = index + delta
    if (target < 0 || target >= next.length) return
    ;[next[index], next[target]] = [next[target], next[index]]
    setEditing({ ...editing, sections: next })
  }

  const toggleSection = (key) => {
    const has = editing.sections.some((s) => s.key === key)
    setEditing({
      ...editing,
      sections: has
        ? editing.sections.filter((s) => s.key !== key)
        : [...editing.sections, { key, title: libraryByKey[key]?.title || key }],
    })
  }

  const renderCard = (format) => (
    <Box key={`${format.source}-${format.key}`} sx={{ p: 2, display: 'flex', flexDirection: 'column', gap: 1.25 }}>
      <Stack direction="row" alignItems="center" gap={1} flexWrap="wrap">
        <Typography sx={{ fontSize: 14, fontWeight: 640 }}>{format.name}</Typography>
        {format.is_default && <Pill tone="accent" dot>default</Pill>}
        <Pill>{format.source === 'client' ? client?.name : 'built-in'}</Pill>
        <Box sx={{ flex: 1 }} />
        {format.source === 'client' && !format.is_default && (
          <Tooltip title="Make this the default">
            <IconButton size="small" onClick={() => setDefault(format)}>
              <StarBorderRoundedIcon sx={{ fontSize: 17 }} />
            </IconButton>
          </Tooltip>
        )}
        {format.is_default && format.source === 'client' && (
          <StarRoundedIcon sx={{ fontSize: 17, color: palette.t.accent }} />
        )}
        <Button size="small" variant="outlined" onClick={() => startEdit(format)}>
          {format.source === 'client' ? 'Edit' : 'Copy to client'}
        </Button>
        {format.source === 'client' && (
          <Tooltip title="Delete this format">
            <IconButton size="small" onClick={() => remove(format)}>
              <DeleteOutlineRoundedIcon sx={{ fontSize: 17 }} />
            </IconButton>
          </Tooltip>
        )}
      </Stack>
      {format.description && (
        <Typography variant="body2" sx={{ color: palette.t.muted }}>{format.description}</Typography>
      )}
      <Stack direction="row" gap={0.75} flexWrap="wrap">
        {format.sections.map((s, i) => (
          <Pill key={`${s.key}-${i}`}>{s.title || s.key}</Pill>
        ))}
      </Stack>
    </Box>
  )

  return (
    <Stack gap={2.25}>
      <Box>
        <Typography variant="h4">Report formats</Typography>
        <Typography variant="body2" sx={{ color: palette.t.muted }}>
          {client
            ? `Which sections ${client.name}'s reports contain, and in what order. The default is used whenever a report is generated without naming a format.`
            : 'Pick a client in the top bar.'}
        </Typography>
      </Box>

      {loading && <LinearProgress />}
      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}
      {notice && <Alert severity="success" onClose={() => setNotice(null)}>{notice}</Alert>}

      <Stack direction="row" alignItems="center" gap={1.5} flexWrap="wrap">
        <Label>{own.length} client format{own.length === 1 ? '' : 's'}</Label>
        <Box sx={{ flex: 1 }} />
        <Button variant="contained" startIcon={<AddRoundedIcon />} onClick={startNew} disabled={!clientId}>
          New format
        </Button>
      </Stack>

      {own.length ? (
        <HGrid columns={1}>{own.map(renderCard)}</HGrid>
      ) : (
        <Panel>
          <EmptyState
            title="No format of its own yet"
            body={`${client?.name || 'This client'} falls back to the built-in default. Create a format to choose its sections.`}
            action={<Button variant="contained" onClick={startNew}>New format</Button>}
          />
        </Panel>
      )}

      <Box>
        <Typography variant="h5" sx={{ mb: 1.25 }}>Built-in layouts</Typography>
        <Typography variant="body2" sx={{ color: palette.t.muted, mb: 1.5 }}>
          Starting points. Copy one to this client, then add or remove sections.
        </Typography>
        <HGrid columns={1}>{stock.map(renderCard)}</HGrid>
      </Box>

      <Dialog open={!!editing} onClose={() => setEditing(null)} fullWidth maxWidth="md">
        <DialogTitle sx={{ fontSize: 17, fontWeight: 640 }}>
          {editing?.isNew ? 'New report format' : 'Edit report format'}
        </DialogTitle>
        <DialogContent dividers>
          {editing && (
            <Stack gap={2} sx={{ pt: 1 }}>
              <Stack direction="row" gap={1.5} flexWrap="wrap">
                <TextField
                  size="small" label="Name" sx={{ flex: 1, minWidth: 200 }}
                  value={editing.name}
                  onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                />
                <TextField
                  size="small" label="Key" sx={{ width: 190 }}
                  helperText="unique within this client"
                  value={editing.key}
                  onChange={(e) => setEditing({ ...editing, key: e.target.value })}
                />
                <Box sx={{ minWidth: 190 }}>
                  <Label>Base layout</Label>
                  <Select
                    size="small" fullWidth value={editing.base_key}
                    onChange={(e) => setEditing({ ...editing, base_key: e.target.value })}
                  >
                    {builtIn.map((b) => <MenuItem key={b.key} value={b.key}>{b.label}</MenuItem>)}
                  </Select>
                </Box>
              </Stack>

              <TextField
                size="small" label="Description" multiline minRows={2}
                value={editing.description}
                onChange={(e) => setEditing({ ...editing, description: e.target.value })}
              />

              <Stack direction="row" alignItems="center" gap={1}>
                <Checkbox
                  size="small" checked={editing.is_default}
                  onChange={(e) => setEditing({ ...editing, is_default: e.target.checked })}
                />
                <Typography variant="body2">
                  Use this format by default for {client?.name}
                </Typography>
              </Stack>

              <Box>
                <Typography variant="h6" sx={{ mb: 0.75 }}>Sections in this report</Typography>
                <Typography variant="body2" sx={{ color: palette.t.muted, mb: 1.25 }}>
                  Order here is the order of sheets in the workbook.
                </Typography>
                <HGrid columns={1}>
                  {editing.sections.map((s, i) => (
                    <Stack key={`${s.key}-${i}`} direction="row" alignItems="center" gap={1} sx={{ px: 1.5, py: 1 }}>
                      <Box sx={{ fontSize: 11, color: palette.t.faint, width: 22 }}>{i + 1}</Box>
                      <TextField
                        size="small" variant="standard" sx={{ flex: 1 }}
                        value={s.title || ''}
                        onChange={(e) => {
                          const next = [...editing.sections]
                          next[i] = { ...next[i], title: e.target.value }
                          setEditing({ ...editing, sections: next })
                        }}
                      />
                      <Pill>{s.key}</Pill>
                      <IconButton size="small" onClick={() => move(i, -1)} disabled={i === 0}>
                        <ArrowUpwardRoundedIcon sx={{ fontSize: 15 }} />
                      </IconButton>
                      <IconButton size="small" onClick={() => move(i, 1)} disabled={i === editing.sections.length - 1}>
                        <ArrowDownwardRoundedIcon sx={{ fontSize: 15 }} />
                      </IconButton>
                      <IconButton size="small" onClick={() => toggleSection(s.key)}>
                        <DeleteOutlineRoundedIcon sx={{ fontSize: 15 }} />
                      </IconButton>
                    </Stack>
                  ))}
                </HGrid>
              </Box>

              <Box>
                <Typography variant="h6" sx={{ mb: 0.75 }}>Available sections</Typography>
                <Stack gap={0.75}>
                  {library.map((s) => {
                    const on = editing.sections.some((x) => x.key === s.key)
                    return (
                      <Stack key={s.key} direction="row" alignItems="flex-start" gap={1}>
                        <Checkbox size="small" checked={on} onChange={() => toggleSection(s.key)} sx={{ mt: -0.5 }} />
                        <Box sx={{ flex: 1 }}>
                          <Stack direction="row" gap={0.75} alignItems="center" flexWrap="wrap">
                            <Typography variant="body2" sx={{ fontWeight: 600 }}>{s.title}</Typography>
                            {s.requires.map((r) => (
                              <Pill key={r} tone={r === 'leads' || r === 'sale_grading' ? 'warn' : 'neutral'}>
                                {REQUIRE_LABEL[r] || r}
                              </Pill>
                            ))}
                          </Stack>
                          <Typography variant="caption" sx={{ color: palette.t.muted }}>
                            {s.description}
                          </Typography>
                        </Box>
                      </Stack>
                    )
                  })}
                </Stack>
              </Box>
            </Stack>
          )}
        </DialogContent>
        <DialogActions sx={{ px: 3, py: 2 }}>
          <Button onClick={() => setEditing(null)}>Cancel</Button>
          <Button
            variant="contained" onClick={save}
            disabled={!editing?.name?.trim() || !editing?.key?.trim() || !editing?.sections?.length}
          >
            Save format
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  )
}

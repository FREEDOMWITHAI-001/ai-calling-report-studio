import { useEffect, useState } from 'react'
import {
  Alert, Box, Button, Card, CardContent, Chip, FormControl, Grid, InputLabel, MenuItem,
  Select, Stack, Table, TableBody, TableCell, TableHead, TableRow, TextField, Typography,
} from '@mui/material'
import { api } from '../api.js'
import { useApp } from '../state/AppState.jsx'

const NUMERIC = ['sale_value', 'cost_per_minute', 'connect_threshold_s', 'attendance_match_days']
const CHOICES = {
  billing_rounding: ['ceil_minute', 'exact_second'],
  baseline_mode: ['not_connected', 'never_dialled', 'no_bot_reached'],
  uplift_mode: ['weighted', 'simple'],
  attendance_match_mode: ['window', 'same_day'],
}
const LISTS = ['signup_bot_patterns', 'dayof_bot_patterns', 'team_email_domains', 'team_name_patterns',
  'team_phones', 'age_band_edges', 'match_keys']

export default function SettingsPage() {
  const { clientId } = useApp()
  const [params, setParams] = useState(null)
  const [saved, setSaved] = useState([])
  const [bots, setBots] = useState([])
  const [name, setName] = useState('Custom methodology')
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)

  useEffect(() => {
    if (!clientId) return
    setBots([])
    Promise.all([api.methodologyDefaults(), api.methodologies(), api.bots()])
      .then(([defaults, list, botList]) => {
        const active = list.find((m) => m.is_default)
        setParams(active ? { ...defaults, ...active.params } : defaults)
        setSaved(list)
        setBots(botList)
        if (active) setName(active.name)
      })
      .catch((e) => setError(e.message))
  }, [clientId])

  const update = (key, value) => setParams((prev) => ({ ...prev, [key]: value }))

  const save = async () => {
    setError(null)
    try {
      await api.saveMethodology({ name, params, is_default: true })
      setSaved(await api.methodologies())
      setNotice('Saved and set as the default for new reports.')
    } catch (e) { setError(e.message) }
  }

  const setBotRole = async (bot, role) => {
    await api.updateBot(bot.id, { role })
    setBots(await api.bots())
  }

  if (!params) return <Typography>Loading…</Typography>

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4">Methodology</Typography>
        <Typography variant="body2" color="text.secondary">
          Every number in the report traces back to these settings — nothing is hardcoded.
        </Typography>
      </Box>

      {error && <Alert severity="error" onClose={() => setError(null)}>{error}</Alert>}
      {notice && <Alert severity="success" onClose={() => setNotice(null)}>{notice}</Alert>}

      <Card>
        <CardContent>
          <Grid container spacing={2}>
            {NUMERIC.map((key) => (
              <Grid item xs={12} sm={6} md={3} key={key}>
                <TextField fullWidth size="small" type="number" label={key.replace(/_/g, ' ')}
                  value={params[key] ?? ''} onChange={(e) => update(key, Number(e.target.value))} />
              </Grid>
            ))}
            {Object.entries(CHOICES).map(([key, values]) => (
              <Grid item xs={12} sm={6} md={3} key={key}>
                <FormControl fullWidth size="small">
                  <InputLabel>{key.replace(/_/g, ' ')}</InputLabel>
                  <Select label={key.replace(/_/g, ' ')} value={params[key] ?? values[0]}
                    onChange={(e) => update(key, e.target.value)}>
                    {values.map((v) => <MenuItem key={v} value={v}>{v}</MenuItem>)}
                  </Select>
                </FormControl>
              </Grid>
            ))}
            {LISTS.map((key) => (
              <Grid item xs={12} md={6} key={key}>
                <TextField fullWidth size="small" label={`${key.replace(/_/g, ' ')} (comma separated)`}
                  value={(params[key] || []).join(', ')}
                  onChange={(e) => update(key, e.target.value.split(',').map((v) => v.trim()).filter(Boolean)
                    .map((v) => (key === 'age_band_edges' ? Number(v) : v)))} />
              </Grid>
            ))}
          </Grid>

          <Stack direction="row" spacing={2} sx={{ mt: 3 }} alignItems="center">
            <TextField size="small" label="Save as" value={name} onChange={(e) => setName(e.target.value)} />
            <Button variant="contained" onClick={save}>Save &amp; make default</Button>
            {saved.map((m) => (
              <Chip key={m.id} label={m.name} color={m.is_default ? 'primary' : 'default'} size="small" />
            ))}
          </Stack>
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>Bot roles</Typography>
          <Typography variant="caption" color="text.secondary">
            Signup and day-of bots define "connected" and the billed talk cost. Everything else is ignored by the
            impact calculation unless you pick it explicitly when generating a report.
          </Typography>
          <Table size="small" sx={{ mt: 2 }}>
            <TableHead>
              <TableRow>
                <TableCell>Bot</TableCell>
                <TableCell>Language</TableCell>
                <TableCell width={200}>Role</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {bots.map((bot) => (
                <TableRow key={bot.id}>
                  <TableCell>{bot.name}</TableCell>
                  <TableCell>{bot.language || '—'}</TableCell>
                  <TableCell>
                    <Select size="small" fullWidth value={bot.role} onChange={(e) => setBotRole(bot, e.target.value)}>
                      <MenuItem value="signup">signup</MenuItem>
                      <MenuItem value="day_of">day_of</MenuItem>
                      <MenuItem value="other">other</MenuItem>
                    </Select>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </Stack>
  )
}

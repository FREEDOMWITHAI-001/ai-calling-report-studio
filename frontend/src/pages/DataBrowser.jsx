import { useEffect, useState } from 'react'
import {
  Alert, Box, Card, CardContent, Paper, Stack, Tab, Table, TableBody, TableCell, TableHead,
  TableRow, Tabs, Typography,
} from '@mui/material'
import { api, fmt } from '../api.js'
import { useApp } from '../state/AppState.jsx'

const TABLES = [
  { key: 'registrations', label: 'Registrations' },
  { key: 'ai_calls', label: 'AI calls' },
  { key: 'sales', label: 'Sales' },
  { key: 'attendance', label: 'Attendance' },
  { key: 'webinar_daily', label: 'Platform daily' },
  { key: 'persons', label: 'People' },
  { key: 'generic', label: 'Custom data' },
]

export default function DataBrowser() {
  const { clientId } = useApp()
  const [table, setTable] = useState('registrations')
  const [rows, setRows] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    setError(null)
    setRows([])
    if (!clientId) return
    api.rows(table, 100).then((data) => setRows(data.rows || [])).catch((e) => setError(e.message))
  }, [table, clientId])

  const columns = rows.length ? Object.keys(rows[0]) : []

  return (
    <Stack spacing={3}>
      <Box>
        <Typography variant="h4">Data</Typography>
        <Typography variant="body2" color="text.secondary">
          The normalized tables the reports are built from — latest 100 rows per table.
        </Typography>
      </Box>

      {error && <Alert severity="error">{error}</Alert>}

      <Card>
        <CardContent>
          <Tabs value={table} onChange={(_, value) => setTable(value)} variant="scrollable" scrollButtons="auto">
            {TABLES.map((t) => <Tab key={t.key} value={t.key} label={t.label} />)}
          </Tabs>
          <Paper variant="outlined" sx={{ mt: 2, overflowX: 'auto', maxHeight: 620 }}>
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  {columns.map((col) => (
                    <TableCell key={col} sx={{ whiteSpace: 'nowrap', fontWeight: 700 }}>{col}</TableCell>
                  ))}
                </TableRow>
              </TableHead>
              <TableBody>
                {rows.map((row, index) => (
                  <TableRow key={index} hover>
                    {columns.map((col) => (
                      <TableCell key={col} sx={{ whiteSpace: 'nowrap', maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {typeof row[col] === 'object' && row[col] !== null
                          ? JSON.stringify(row[col]).slice(0, 60)
                          : String(row[col] ?? '')}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
                {!rows.length && (
                  <TableRow><TableCell>
                    <Typography variant="body2" color="text.secondary" sx={{ p: 2 }}>No rows.</Typography>
                  </TableCell></TableRow>
                )}
              </TableBody>
            </Table>
          </Paper>
        </CardContent>
      </Card>
    </Stack>
  )
}

import { Table, TableBody, TableCell, TableHead, TableRow, Typography, useTheme } from '@mui/material'
import { Delta } from './ui/index.jsx'
import { fmt } from '../api.js'

export default function GroupTable({ rows = [], dense = false }) {
  const { palette } = useTheme()

  return (
    <Table size={dense ? 'small' : 'medium'}>
      <TableHead>
        <TableRow>
          <TableCell>Group</TableCell>
          <TableCell align="right">Registrants</TableCell>
          <TableCell align="right">Showed</TableCell>
          <TableCell align="right">Show-up&nbsp;%</TableCell>
          <TableCell align="right">Show-up&nbsp;Δ</TableCell>
          <TableCell align="right">Buyers</TableCell>
          <TableCell align="right">Buyer&nbsp;%</TableCell>
          <TableCell align="right">Buyer&nbsp;Δ</TableCell>
        </TableRow>
      </TableHead>
      <TableBody>
        {rows.map((row, index) => {
          const isTotal = row.key === 'total'
          const isBaseline = row.key === 'baseline'
          return (
            <TableRow
              key={`${row.key || row.label}-${index}`}
              sx={{
                // Tokens, not literals — these rows have to read in both themes.
                background: isTotal ? palette.t.panel2 : isBaseline ? palette.t.warnSoft : 'transparent',
                '& td': { fontWeight: isTotal ? 660 : 400, fontVariantNumeric: 'tabular-nums' },
              }}
            >
              <TableCell sx={{ fontVariantNumeric: 'normal !important' }}>
                <Typography variant="body2" sx={{ fontWeight: isTotal ? 660 : 540 }}>
                  {row.label || row.key || '—'}
                </Typography>
              </TableCell>
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
        {!rows.length && (
          <TableRow>
            <TableCell colSpan={8}>
              <Typography variant="body2" color="text.secondary">No groups in this window.</Typography>
            </TableCell>
          </TableRow>
        )}
      </TableBody>
    </Table>
  )
}

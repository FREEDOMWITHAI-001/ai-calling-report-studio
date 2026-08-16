import { Box, Stack, Typography, useTheme } from '@mui/material'
import { Label } from './ui/index.jsx'

export default function MetricCard({ label, value, sub, accent = false }) {
  const { palette } = useTheme()
  return (
    <Box
      sx={{
        height: '100%',
        borderRadius: '12px',
        border: `1px solid ${accent ? 'transparent' : palette.t.border}`,
        background: accent ? palette.t.accentSoft : palette.t.panel,
        p: 1.9,
      }}
    >
      <Stack gap={0.75}>
        <Label sx={accent ? { color: palette.t.accent } : undefined}>{label}</Label>
        <Typography
          sx={{
            fontSize: 26,
            lineHeight: 1.05,
            fontWeight: 660,
            letterSpacing: '-.03em',
            fontVariantNumeric: 'tabular-nums',
            color: accent ? palette.t.accent : palette.t.text,
          }}
        >
          {value}
        </Typography>
        {sub && (
          <Typography variant="caption" sx={{ color: accent ? palette.t.accent : palette.t.muted, opacity: accent ? 0.85 : 1 }}>
            {sub}
          </Typography>
        )}
      </Stack>
    </Box>
  )
}

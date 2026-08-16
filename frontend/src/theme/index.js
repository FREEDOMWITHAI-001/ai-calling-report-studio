import { createTheme } from '@mui/material/styles'
import { FONT_MONO, FONT_UI, tokens } from './tokens.js'

/**
 * Builds the MUI theme for a mode. Every colour comes from `tokens`; the raw
 * token set is also exposed as `theme.palette.t` so components can reach values
 * MUI has no slot for (panel2, faint, accentSoft, …).
 */
export function buildTheme(mode) {
  const t = tokens[mode]

  return createTheme({
    palette: {
      mode,
      t,
      primary: { main: t.accent, contrastText: t.btnFg },
      secondary: { main: t.muted },
      success: { main: t.pos },
      warning: { main: t.warn },
      error: { main: t.crit },
      background: { default: t.bg, paper: t.panel },
      text: { primary: t.text, secondary: t.muted, disabled: t.faint },
      divider: t.border,
      action: { hover: t.panel2, selected: t.accentSoft },
    },

    shape: { borderRadius: 10 },

    typography: {
      fontFamily: FONT_UI,
      fontSize: 14,
      h4: { fontSize: 26, fontWeight: 650, letterSpacing: '-.025em' },
      h5: { fontSize: 19, fontWeight: 640, letterSpacing: '-.02em' },
      h6: { fontSize: 15, fontWeight: 640, letterSpacing: '-.01em' },
      subtitle2: { fontSize: 12.5, fontWeight: 600 },
      body1: { fontSize: 14 },
      body2: { fontSize: 13 },
      caption: { fontSize: 12, color: t.muted },
      overline: {
        fontFamily: FONT_MONO,
        fontSize: 9.5,
        letterSpacing: '.13em',
        fontWeight: 600,
        lineHeight: 1.6,
      },
      button: { textTransform: 'none', fontWeight: 600 },
    },

    components: {
      MuiCssBaseline: {
        styleOverrides: {
          '*': { boxSizing: 'border-box' },
          body: { backgroundColor: t.bg, color: t.text, WebkitFontSmoothing: 'antialiased' },
          '::selection': { background: t.accentSoft, color: t.accent },
          '*::-webkit-scrollbar': { width: 10, height: 10 },
          '*::-webkit-scrollbar-thumb': {
            background: t.borderStrong,
            borderRadius: 99,
            border: `3px solid ${t.bg}`,
          },
          '*::-webkit-scrollbar-track': { background: 'transparent' },
          '@media (prefers-reduced-motion: reduce)': {
            '*': { transition: 'none !important', animation: 'none !important' },
          },
        },
      },
      MuiPaper: { styleOverrides: { root: { backgroundImage: 'none' } } },
      MuiButton: {
        defaultProps: { disableElevation: true },
        styleOverrides: {
          root: { borderRadius: 8, fontSize: 12.5, paddingInline: 13 },
          contained: { background: t.btnBg, color: t.btnFg, '&:hover': { background: t.btnBg, filter: 'brightness(1.08)' } },
          outlined: { borderColor: t.border, background: t.panel2, color: t.text, '&:hover': { borderColor: t.borderStrong, background: t.panel3 } },
        },
      },
      MuiIconButton: { styleOverrides: { root: { borderRadius: 8, color: t.muted, '&:hover': { background: t.panel2, color: t.text } } } },
      MuiChip: {
        styleOverrides: {
          root: { height: 22, fontSize: 11.5, fontWeight: 560, borderRadius: 999 },
          label: { paddingInline: 9 },
          outlined: { borderColor: t.border, background: t.panel2, color: t.muted },
        },
      },
      MuiTooltip: {
        styleOverrides: {
          tooltip: { background: t.text, color: t.bg, fontSize: 11.5, fontWeight: 550, borderRadius: 7 },
          arrow: { color: t.text },
        },
      },
      MuiTableCell: {
        styleOverrides: {
          root: { borderColor: t.border, fontSize: 12.5, padding: '9px 12px' },
          head: {
            fontFamily: FONT_MONO,
            fontSize: 9.5,
            letterSpacing: '.11em',
            textTransform: 'uppercase',
            fontWeight: 600,
            color: t.faint,
            background: t.panel2,
            whiteSpace: 'nowrap',
          },
        },
      },
      MuiDialog: { styleOverrides: { paper: { border: `1px solid ${t.borderStrong}`, boxShadow: t.shadow, borderRadius: 12 } } },
      MuiBackdrop: { styleOverrides: { root: { background: t.scrim } } },
      MuiOutlinedInput: {
        styleOverrides: {
          root: { background: t.panel2, borderRadius: 8, fontSize: 13 },
          notchedOutline: { borderColor: t.border },
        },
      },
      MuiMenu: { styleOverrides: { paper: { border: `1px solid ${t.border}`, boxShadow: t.shadow, borderRadius: 10 } } },
      MuiMenuItem: { styleOverrides: { root: { fontSize: 13, borderRadius: 7, margin: '2px 6px', minHeight: 34 } } },
      MuiAlert: { styleOverrides: { root: { borderRadius: 10, fontSize: 13 } } },
      MuiLinearProgress: { styleOverrides: { root: { background: t.panel3, borderRadius: 99, height: 5 } } },
    },
  })
}

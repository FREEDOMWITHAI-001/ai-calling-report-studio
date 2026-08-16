/**
 * The single source of colour for the whole app.
 *
 * Nothing outside this file may contain a hex value. Components read tokens
 * through the MUI theme (`theme.palette.t.*`) or through the CSS variables
 * injected by `GlobalTokens` (`var(--rs-accent)`), so both themes ship together
 * and a palette change is a one-file change.
 */

const light = {
  bg: '#fbfaff',
  bgSunk: '#f3f1fa',
  panel: '#ffffff',
  panel2: '#f7f6fc',
  panel3: '#efedf8',

  border: '#e5e2f0',
  borderStrong: '#d3cfe4',

  text: '#16141f',
  muted: '#6b6683',
  faint: '#9a95ad',

  accent: '#5b3fe8',
  accentSoft: '#ece8ff',
  accentLine: '#c9beff',
  btnBg: '#5b3fe8',
  btnFg: '#ffffff',

  pos: '#0e8f6a',
  posSoft: '#dbf5ec',
  warn: '#a86f0a',
  warnSoft: '#fbeed2',
  crit: '#cf2740',
  critSoft: '#fde7ea',

  shadow: '0 1px 2px rgba(22,16,50,.05), 0 14px 34px -18px rgba(22,16,50,.28)',
  shadowSoft: '0 1px 2px rgba(22,16,50,.04), 0 6px 16px -10px rgba(22,16,50,.18)',
  ring: '0 0 0 3px rgba(91,63,232,.28)',
  scrim: 'rgba(22,16,50,.34)',
}

const dark = {
  bg: '#0c0c11',
  bgSunk: '#08080c',
  panel: '#15151d',
  panel2: '#1b1b24',
  panel3: '#22222d',

  border: '#26262f',
  borderStrong: '#35353f',

  text: '#f1f0f6',
  muted: '#9490a8',
  faint: '#6a6680',

  accent: '#8b6cff',
  accentSoft: '#221c3d',
  accentLine: '#453a72',
  btnBg: '#7857ff',
  btnFg: '#ffffff',

  pos: '#34d9a4',
  posSoft: '#0f2b24',
  warn: '#e5a63b',
  warnSoft: '#2b2113',
  crit: '#ff6470',
  critSoft: '#2e1419',

  shadow: '0 1px 2px rgba(0,0,0,.5), 0 18px 40px -20px rgba(0,0,0,.8)',
  shadowSoft: '0 1px 2px rgba(0,0,0,.4), 0 8px 20px -12px rgba(0,0,0,.7)',
  ring: '0 0 0 3px rgba(139,108,255,.35)',
  scrim: 'rgba(0,0,0,.58)',
}

export const tokens = { light, dark }

export const FONT_UI =
  'system-ui,-apple-system,"Segoe UI Variable Text","Segoe UI",Roboto,Helvetica,Arial,sans-serif'
export const FONT_MONO =
  'ui-monospace,"Cascadia Mono","SF Mono",Menlo,Consolas,monospace'

/** camelCase token name -> `--rs-kebab-case` custom property. */
export function cssVars(mode) {
  const t = tokens[mode]
  const out = {}
  for (const [k, v] of Object.entries(t)) {
    out[`--rs-${k.replace(/[A-Z]/g, (c) => '-' + c.toLowerCase())}`] = v
  }
  return out
}

// Design tokens for Second Brain mobile — dark, calm, spartan
// Three typography systems explored across variants; shared color + bucket tokens.

const SB = {
  // Canvas / surfaces
  bg:        '#0a0a12',     // deeper than original #0f0f23 — calmer
  surface:   '#13131f',     // card
  surfaceHi: '#1b1b2a',     // elevated card
  hairline:  'rgba(255,255,255,0.06)',
  divider:   'rgba(255,255,255,0.08)',

  // Text
  text:      '#f0f0f5',
  textDim:   'rgba(240,240,245,0.62)',
  textMuted: 'rgba(240,240,245,0.38)',
  textFaint: 'rgba(240,240,245,0.22)',

  // Action / accent (evolved from #4a90d9)
  accent:    '#7a9eff',
  accentDim: 'rgba(122,158,255,0.18)',

  // Status
  recording: '#ff5b5b',
  ok:        '#7ddca0',
  warn:      '#e6b450',
  err:       '#ff6b6b',

  // Bucket colors — muted, desaturated. Each uses oklch-like hue at low chroma.
  buckets: {
    People:   { fg: '#d7c7b4', bg: 'rgba(215,199,180,0.10)', dot: '#b8a387' }, // warm sand
    Projects: { fg: '#a9c5e8', bg: 'rgba(169,197,232,0.10)', dot: '#7fa5cf' }, // dusty blue
    Ideas:    { fg: '#c7bde0', bg: 'rgba(199,189,224,0.10)', dot: '#9d8fbf' }, // muted violet
    Admin:    { fg: '#b8d4c0', bg: 'rgba(184,212,192,0.10)', dot: '#88af96' }, // sage
  },

  // Mode colors (subtle — only used on project detail)
  modes: {
    work:     '#8ca5c7',
    hobby:    '#c79b8c',
    personal: '#a8c78c',
  },
};

// Typography variants — three explorations
const TYPE = {
  // V1: System — SF Pro, iOS-native, tight tracking
  system: {
    label:  '-apple-system, system-ui, "SF Pro Text", Helvetica, Arial, sans-serif',
    body:   '-apple-system, system-ui, "SF Pro Text", Helvetica, Arial, sans-serif',
    display:'-apple-system, system-ui, "SF Pro Display", Helvetica, Arial, sans-serif',
    mono:   'ui-monospace, "SF Mono", Menlo, Consolas, monospace',
  },
  // V2: Mono-accented — technical, showing agent traces as first-class
  mono: {
    label:  'ui-monospace, "SF Mono", "JetBrains Mono", Menlo, monospace',
    body:   '-apple-system, system-ui, "SF Pro Text", sans-serif',
    display:'-apple-system, system-ui, "SF Pro Display", sans-serif',
    mono:   'ui-monospace, "SF Mono", "JetBrains Mono", Menlo, monospace',
  },
  // V3: Serif headline — editorial, calmer, a tiny bit literary
  serif: {
    label:  '"Instrument Sans", -apple-system, system-ui, sans-serif',
    body:   '"Instrument Sans", -apple-system, system-ui, sans-serif',
    display:'"Instrument Serif", "Source Serif Pro", Georgia, serif',
    mono:   '"JetBrains Mono", ui-monospace, "SF Mono", Menlo, monospace',
  },
};

window.SB = SB;
window.TYPE = TYPE;

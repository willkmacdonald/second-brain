/**
 * Design tokens for Second Brain mobile app.
 *
 * All values sourced from the design handoff: docs/ui-design/screens/tokens.jsx
 * Typography direction: V3 Serif (Instrument Serif italic headlines, Instrument Sans body,
 * JetBrains Mono metadata) per D-06/D-08.
 */

export const theme = {
  colors: {
    bg: "#0a0a12",
    surface: "#13131f",
    surfaceHi: "#1b1b2a",
    hairline: "rgba(255,255,255,0.06)",
    divider: "rgba(255,255,255,0.08)",

    text: "#f0f0f5",
    textDim: "rgba(240,240,245,0.62)",
    textMuted: "rgba(240,240,245,0.38)",
    textFaint: "rgba(240,240,245,0.22)",

    accent: "#7a9eff",
    accentDim: "rgba(122,158,255,0.18)",

    recording: "#ff5b5b",
    ok: "#7ddca0",
    warn: "#e6b450",
    err: "#ff6b6b",

    buckets: {
      People: {
        fg: "#d7c7b4",
        bg: "rgba(215,199,180,0.10)",
        dot: "#b8a387",
      },
      Projects: {
        fg: "#a9c5e8",
        bg: "rgba(169,197,232,0.10)",
        dot: "#7fa5cf",
      },
      Ideas: {
        fg: "#c7bde0",
        bg: "rgba(199,189,224,0.10)",
        dot: "#9d8fbf",
      },
      Admin: {
        fg: "#b8d4c0",
        bg: "rgba(184,212,192,0.10)",
        dot: "#88af96",
      },
    },
  },

  fonts: {
    display: "InstrumentSerif_400Regular_Italic",
    body: "InstrumentSans_400Regular",
    bodyMedium: "InstrumentSans_500Medium",
    bodySemiBold: "InstrumentSans_600SemiBold",
    bodyBold: "InstrumentSans_700Bold",
    mono: "JetBrainsMono_400Regular",
  },
} as const;

export type Theme = typeof theme;
export type BucketName = keyof typeof theme.colors.buckets;

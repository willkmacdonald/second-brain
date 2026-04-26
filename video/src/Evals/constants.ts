export const EVALS_FPS = 30;

export const EVALS_SCENES = {
  trigger: { start: 0, duration: 796 },
  results: { start: 796, duration: 521 },
  trend: { start: 1317, duration: 318 },
  spd: { start: 1635, duration: 571 },
} as const;

export const EVALS_TOTAL_DURATION = 2206;

export const EVALS_COLORS = {
  bg: "#05070d",
  panel: "#111827",
  panelSoft: "#161a2b",
  panelGlass: "rgba(17, 24, 39, 0.72)",
  border: "rgba(148, 163, 184, 0.16)",
  text: "#f8fafc",
  muted: "#9ca3af",
  dim: "#6b7280",
  blue: "#58a6ff",
  cyan: "#06b6d4",
  green: "#3fb950",
  amber: "#d29922",
  red: "#ff5d5d",
  purple: "#a78bfa",
} as const;

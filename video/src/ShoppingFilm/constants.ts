export const SHOPPING_FILM_FPS = 30;
export const SHOPPING_FILM_WIDTH = 1920;
export const SHOPPING_FILM_HEIGHT = 1080;
export const SHOPPING_FILM_DURATION = 4286;

export const SCENES = {
  opening: { start: 0, duration: 272 },
  phoneCapture: { start: 272, duration: 601 },
  commerce: { start: 873, duration: 441 },
  techFlow: { start: 1314, duration: 630 },
  classifier: { start: 1944, duration: 477 },
  adminAgent: { start: 2421, duration: 552 },
  observability: { start: 2973, duration: 620 },
  evals: { start: 3593, duration: 370 },
  close: { start: 3963, duration: 323 },
} as const;

export const PALETTE = {
  black: "#050505",
  graphite: "#111113",
  graphite2: "#1b1b1f",
  glass: "rgba(255, 255, 255, 0.08)",
  glassStrong: "rgba(255, 255, 255, 0.14)",
  white: "#f7f7f5",
  softWhite: "#d9dad6",
  muted: "#8b8d91",
  hairline: "rgba(255, 255, 255, 0.18)",
  green: "#35d07f",
  red: "#ff453a",
  blue: "#0a84ff",
  cyan: "#66d9ef",
  gold: "#ffd166",
  violet: "#b7a5ff",
} as const;

export const FONT = {
  sans: "SF Pro Display, Inter, -apple-system, BlinkMacSystemFont, sans-serif",
  text: "SF Pro Text, Inter, -apple-system, BlinkMacSystemFont, sans-serif",
  mono: "SF Mono, Menlo, Consolas, monospace",
} as const;

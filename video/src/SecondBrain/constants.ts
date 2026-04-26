// Color palette
export const COLORS = {
  // Primary
  bgDark: "#0f172a", // slate-900
  bgMedium: "#1e293b", // slate-800
  bgLight: "#334155", // slate-700

  // Accent
  accentBlue: "#3b82f6", // blue-500
  accentCyan: "#06b6d4", // cyan-500
  accentPurple: "#8b5cf6", // violet-500
  accentGreen: "#10b981", // emerald-500
  accentOrange: "#f59e0b", // amber-500
  accentPink: "#ec4899", // pink-500

  // Gradients
  gradientStart: "#3b82f6",
  gradientEnd: "#8b5cf6",

  // Text
  textWhite: "#f8fafc",
  textGray: "#94a3b8",
  textDim: "#64748b",

  // Bucket colors
  bucketPeople: "#3b82f6",
  bucketProjects: "#10b981",
  bucketIdeas: "#f59e0b",
  bucketAdmin: "#ec4899",
};

// Timing (frames at 30fps)
export const FPS = 30;

// Timings matched to voiceover.mp3 (~139s) via silence detection
export const SECTIONS = {
  intro: { start: 0, duration: 420 },        // 0-14s (420 frames)
  whatItIs: { start: 420, duration: 690 },    // 14-37s (690 frames)
  vision: { start: 1110, duration: 870 },     // 37-66s (870 frames)
  howItWorks: { start: 1980, duration: 720 }, // 66-90s (720 frames)
  future: { start: 2700, duration: 1290 },    // 90-133s (1290 frames)
  outro: { start: 3990, duration: 200 },      // 133-139.6s (200 frames)
} as const;

export const TOTAL_DURATION = 4190; // ~139.7s at 30fps

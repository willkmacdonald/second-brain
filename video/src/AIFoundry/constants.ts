export const COLORS = {
  bgDark: "#0f172a",
  bgMedium: "#1e293b",
  bgLight: "#334155",

  accentBlue: "#3b82f6",
  accentCyan: "#06b6d4",
  accentPurple: "#8b5cf6",
  accentGreen: "#10b981",
  accentOrange: "#f59e0b",
  accentPink: "#ec4899",

  gradientStart: "#3b82f6",
  gradientEnd: "#8b5cf6",

  textWhite: "#f8fafc",
  textGray: "#94a3b8",
  textDim: "#64748b",
};

export const FPS = 30;

// Current voiceover is 120.555 seconds. Scene starts are aligned to the
// paragraph pauses detected in breakout-ai-foundry.mp3.
export const SCENES = {
  agentPanel: { start: 0, duration: 1395 },       // 0:00-0:46.5
  instructions: { start: 1395, duration: 779 },   // 0:46.5-1:12.5
  handoff: { start: 2174, duration: 650 },        // 1:12.5-1:34.1
  splitScreen: { start: 2824, duration: 793 },    // 1:34.1-2:00.6
} as const;

export const TOTAL_DURATION = 3617;

export const BUILT_AGENTS = [
  { name: "Orchestrator", role: "routes every input", color: "#58a6ff" },
  { name: "Classifier", role: "Admin · Projects · People · Ideas", color: COLORS.accentBlue },
  { name: "Admin Agent", role: "routes errands to destinations", color: COLORS.accentGreen },
  { name: "Investigation Agent", role: "observability + evaluation tools", color: COLORS.accentPurple },
] as const;

export const DEVELOPMENT_AGENTS = [
  { name: "Idea Connector", role: "Links new thoughts to older ideas", color: COLORS.accentOrange },
  { name: "People Agent", role: "Organizes relationship context", color: COLORS.accentOrange },
  { name: "Digest Agent", role: "Composes the morning briefing", color: COLORS.accentOrange },
] as const;

export const SECOND_BRAIN_CHAIN = [
  { name: "Orchestrator", role: "Receives input", color: COLORS.accentCyan },
  { name: "Classifier", role: "Classifies bucket", color: COLORS.accentBlue },
  { name: "Admin Agent", role: "Routes admin work", color: COLORS.accentGreen },
] as const;

export const SECOND_BRAIN_INDEPENDENT = [
  { name: "Idea Connector", role: "Scheduled idea linking", color: COLORS.accentOrange },
  { name: "Digest Agent", role: "Scheduled morning brief", color: COLORS.accentOrange },
] as const;

export const SPD_AGENTS = [
  { name: "Orchestrator", role: "Routes sterile processing events", color: COLORS.accentCyan },
  { name: "Compliance Agent", role: "compliance checks", color: COLORS.accentBlue },
  { name: "Routing Agent", role: "tray routing", color: COLORS.accentGreen },
  { name: "Prediction Agent", role: "predictive maintenance", color: COLORS.accentOrange },
] as const;

export const SPD_INDEPENDENT = [
  { name: "Quality Trend Analyzer", role: "Scheduled quality scans", color: COLORS.accentOrange },
  { name: "Shift Briefing Agent", role: "Scheduled shift summary", color: COLORS.accentOrange },
] as const;

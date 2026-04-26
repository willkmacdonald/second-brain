import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const files = [
  "src/Root.tsx",
  "src/AIFoundry/constants.ts",
  "src/AIFoundry/index.tsx",
  "src/AIFoundry/AgentPanelScene.tsx",
  "src/AIFoundry/InstructionsScene.tsx",
  "src/AIFoundry/HandoffScene.tsx",
  "src/AIFoundry/SplitScreenScene.tsx",
].map((file) => path.join(root, file));

const source = files.map((file) => fs.readFileSync(file, "utf8")).join("\n");

const required = [
  "BreakoutAIFoundry",
  "breakout-ai-foundry.mp3",
  "Azure AI Foundry",
  "Orchestrator",
  "Classifier",
  "Admin Agent",
  "Investigation Agent",
  "observability + evaluation tools",
  "Idea Connector",
  "People Agent",
  "Digest Agent",
  "Managed Instructions",
  "Every agent has one job",
  "Admin · Projects · People · Ideas",
  "file_to_bucket",
  "The orchestrator transfers control",
  "Filed → Admin",
  "Chewy.com",
  "auto-order",
  "independent schedule",
  "Sterile Processing",
  "Compliance Agent",
  "compliance checks",
  "Routing Agent",
  "tray routing",
  "Prediction Agent",
  "predictive maintenance",
  "sterilizer cycle",
  "Same patterns, different domain",
];

const missing = required.filter((term) => !source.includes(term));
const forbidden = [
  "Perception Agent",
  "Action Agent",
  "Telemetry Ingest",
];
const presentForbidden = forbidden.filter((term) => source.includes(term));

if (missing.length > 0 || presentForbidden.length > 0) {
  console.error("BreakoutAIFoundry verification failed.");
  if (missing.length > 0) {
    console.error(`Missing required terms:\n- ${missing.join("\n- ")}`);
  }
  if (presentForbidden.length > 0) {
    console.error(`Forbidden old terms still present:\n- ${presentForbidden.join("\n- ")}`);
  }
  process.exit(1);
}

console.log(`BreakoutAIFoundry verification passed (${required.length} checks).`);

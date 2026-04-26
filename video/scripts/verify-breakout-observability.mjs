import fs from "node:fs";
import path from "node:path";

const root = process.cwd();
const files = [
  "src/Root.tsx",
  "src/Observability/constants.ts",
  "src/Observability/index.tsx",
].map((file) => path.join(root, file));

const source = files.map((file) => fs.readFileSync(file, "utf8")).join("\n");

const required = [
  "BreakoutObservability",
  "observability.mp3",
  "Application Insights + OpenTelemetry",
  "Distributed tracing across every agent",
  "Requests",
  "Avg Response",
  "Failed",
  "Second Brain — Spine",
  "Live request stream",
  "trace_id=txn_9f42",
  "Transaction Path",
  "backend_api",
  "Recent requests (200)",
  "GET /health",
  "Mobile Capture",
  "API Gateway",
  "Orchestrator → Classifier",
  "file_to_bucket",
  "Orchestrator → Admin Agent",
  "Cosmos DB Write",
  "GPT-4o",
  "0.85",
  "Admin",
  "Jewel-Osco",
  "Compliance lens",
  "Mobile Scan",
  "Compliance Agent",
  "confidence: 0.97",
  "Routing Agent",
  "Every decision. Every model. Every timestamp.",
  "that's evidence",
];

const missing = required.filter((term) => !source.includes(term));

if (missing.length > 0) {
  console.error("BreakoutObservability verification failed.");
  console.error(`Missing required terms:\n- ${missing.join("\n- ")}`);
  process.exit(1);
}

console.log(`BreakoutObservability verification passed (${required.length} checks).`);

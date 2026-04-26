import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = process.cwd();
const files = [
  "src/Evals/index.tsx",
  "src/Evals/constants.ts",
  "src/Root.tsx",
  "package.json",
].map((file) => [file, readFileSync(join(root, file), "utf8")]);

const corpus = files.map(([, text]) => text).join("\n");
const requiredTerms = [
  "BreakoutEvals",
  "BreakoutEvalsVideo",
  "breakout-evals.mp3",
  "Run classifier eval",
  "investigation agent",
  "Eval results are readable",
  "Failure Patterns",
  "Projects vs Ideas confusion",
  "Classifier Accuracy",
  "Capture",
  "Action",
  "Evidence",
  "Improve",
  "Compliance Agent Accuracy",
  "Sterilize",
  "Validate",
  "Trace",
  "Auditable.",
  "Explainable.",
  "Improvable.",
];

const missing = requiredTerms.filter((term) => !corpus.includes(term));

if (missing.length > 0) {
  console.error(`BreakoutEvals verification failed. Missing: ${missing.join(", ")}`);
  process.exit(1);
}

console.log(`BreakoutEvals verification passed (${requiredTerms.length} checks).`);

import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const root = process.cwd();
const requiredFiles = [
  "src/ShoppingFilm/index.tsx",
  "src/ShoppingFilm/storyboard.ts",
  "src/ShoppingFilm/constants.ts",
  "SHOPPING_FILM_VOICEOVER.md",
];

for (const file of requiredFiles) {
  if (!existsSync(join(root, file))) {
    throw new Error(`Missing required shopping film file: ${file}`);
  }
}

const rootSource = readFileSync(join(root, "src/Root.tsx"), "utf8");
if (!rootSource.includes('id="SecondBrainShoppingFilm"')) {
  throw new Error("SecondBrainShoppingFilm composition is not registered");
}

const storyboard = readFileSync(join(root, "src/ShoppingFilm/storyboard.ts"), "utf8");
const composition = readFileSync(join(root, "src/ShoppingFilm/index.tsx"), "utf8");
const constants = readFileSync(join(root, "src/ShoppingFilm/constants.ts"), "utf8");
const requiredTerms = [
  "Chewy",
  "automatic order placement",
  "green light / red light",
  "Listening",
  "Classifying",
  "front to back",
  "classifier",
  "observability",
  "eval",
  "self improvement",
];

for (const term of requiredTerms) {
  if (!storyboard.toLowerCase().includes(term.toLowerCase())) {
    throw new Error(`Storyboard is missing required term: ${term}`);
  }
}

const requiredRenderedTerms = [
  "Tap to record",
  "Listening...",
  "Classifying...",
  "Capture",
  "Inbox",
  "Shopping list",
  "Jewel-Osco",
  "Processing 1 new capture...",
  "onions",
  "garlic",
  "cilantro",
  "CVS",
  "Agora",
  "cat food",
  "Tasks",
  "Run classifier eval",
  "Show eval results",
  "Captures (24h)",
  "Success Rate",
  "Errors (24h)",
  "Recent errors",
  "Today's captures",
  "System health",
  "Do an email run on classifier",
  "golden dataset",
  "96.15%",
  "Calibration",
  "Overall Accuracy",
  "Status",
  "Microsoft Foundry",
  "My agents",
  "OB-classifier",
  "InvestigationAgent",
  "AdminAgent",
  "Classifier Agent",
  "Admin Agent",
  "Agent instructions",
  "file_capture tool",
  "automatic order placement only when the item matches a trusted",
  "second-brain-insights",
  "Application Insights",
  "Failed requests",
  "Server response time",
  "Server requests",
  "Availability",
  "Chewy Connector",
];

for (const term of requiredRenderedTerms) {
  if (!composition.includes(term)) {
    throw new Error(`Composition is missing rendered phone UI term: ${term}`);
  }
}

const forbiddenPhoneTerms = [
  "Snell Roundhand",
  "Apple Chancery",
  "fontStyle: \"italic\"",
  "PhoneStatusBar",
];

for (const term of forbiddenPhoneTerms) {
  if (composition.includes(term)) {
    throw new Error(`Composition still includes distracting phone UI styling: ${term}`);
  }
}

if (!composition.includes("Arial, Helvetica, sans-serif")) {
  throw new Error("Phone UI must use Arial typography.");
}

if (!composition.includes('staticFile("fortive-demo-intro.mp3")')) {
  throw new Error("SecondBrainShoppingFilm must use public/fortive-demo-intro.mp3.");
}

if (!constants.includes("SHOPPING_FILM_DURATION = 4286")) {
  throw new Error("Shopping film duration must match fortive-demo-intro.mp3 (~142.84s).");
}

const expectedSceneCuts = [
  "opening: { start: 0, duration: 272 }",
  "phoneCapture: { start: 272, duration: 601 }",
  "commerce: { start: 873, duration: 441 }",
  "techFlow: { start: 1314, duration: 630 }",
  "classifier: { start: 1944, duration: 477 }",
  "adminAgent: { start: 2421, duration: 552 }",
  "observability: { start: 2973, duration: 620 }",
  "evals: { start: 3593, duration: 370 }",
  "close: { start: 3963, duration: 323 }",
];

for (const cut of expectedSceneCuts) {
  if (!constants.includes(cut)) {
    throw new Error(`Shopping film scene timing is not aligned: ${cut}`);
  }
}

console.log("Shopping film structure verified.");

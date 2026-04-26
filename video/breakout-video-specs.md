# Breakout Video Specs

## Video A: AI Foundry — The Agent Orchestration Layer

**Composition ID:** `BreakoutAIFoundry`

**Audio file:** `video/public/breakout-ai-foundry.mp3`

**Voiceover script:**

This is Azure AI Foundry. It’s where the agent layer is defined, deployed, and inspected.

In my app, the agent team has four built agents today. The orchestrator receives every input and decides where control should go. The classifier decides whether a capture belongs in Admin, Projects, People, or Ideas. The Admin Agent turns errands and purchases into routed actions. And the Investigation Agent exposes observability and evaluation tools.

There are also agents in development: an Idea Connector, a People Agent, and a Digest Agent. Same platform, different responsibilities.

Each agent has managed instructions: a system prompt that defines exactly what it does, what it must not do, and which tools it can call. The classifier does not route shopping destinations. The Admin Agent does not classify buckets. The Investigation Agent does not file captures. Each agent has one job and a strict contract.

The handoff pattern is the key. The orchestrator receives the request, transfers control to the classifier, then hands the Admin work to the Admin Agent. In parallel, scheduled agents can run independently, like the Idea Connector or Digest Agent, without waiting for a user request.

For sterile processing, the pattern is identical. Your orchestrator routes incoming data: sterilizer telemetry, instrument scans, and quality events. Specialist agents handle compliance checks, tray routing, predictive maintenance, quality trends, and shift briefings. Same architecture, different domain.

**Composition prompt — what to build visually:**

1. **Scene 1 — Agent Roster:** Dark stage. Fade in a stylized AI Foundry panel with two groups of agent cards. Built group with green status dots: Orchestrator, Classifier, Admin Agent, Investigation Agent. Investigation Agent role line: "observability + evaluation tools". In Development group with amber status dots: Idea Connector, People Agent, Digest Agent. Stagger card entrances, built group first, then in-development group slightly muted.

2. **Scene 2 — Managed Instructions:** Zoom into the Classifier agent card. Expand into a glass "Managed Instructions" panel showing bucket definitions, confidence threshold, and allowed tools. Highlight the `file_to_bucket` tool contract. Emphasize that each agent has a strict, inspectable contract.

3. **Scene 3 — Orchestration Patterns:** Show two patterns. Pattern 1: Orchestrator -> Classifier -> Admin Agent as a cyan-pulsing handoff chain. Admin Agent then routes to Jewel-Osco, CVS, Chewy.com, and Tasks. Pattern 2: Idea Connector and Digest Agent pulse on their own rhythm with a clock icon and label "independent schedule." Two patterns, one platform.

4. **Scene 4 — SPD Bridge:** Compress the Second Brain constellation to the left. Fade in the SPD equivalent on the right: Orchestrator -> Compliance Agent -> Routing Agent -> Prediction Agent. A sterilizer cycle icon enters the chain. Independent SPD agents: Quality Trend Analyzer and Shift Briefing Agent. Close with both constellations side by side and a shared "Azure AI Foundry" bar.

# BreakoutAIFoundry Voiceover

This is Azure AI Foundry. It's where you define, deploy, and manage AI agents.

In my app, the agent team has four built agents today. The orchestrator receives every input and decides where control should go. The classifier decides whether a capture belongs in Admin, Projects, People, or Ideas. The Admin Agent turns errands and purchases into routed actions. And the Investigation Agent exposes observability and evaluation tools.

There are also agents in development: an Idea Connector, a People Agent, and a Digest Agent. Same platform, different responsibilities.

Each agent has managed instructions: a system prompt that defines exactly what it does, what it must not do, and which tools it can call. The classifier does not route shopping destinations. The Admin Agent does not classify buckets. The Investigation Agent does not file captures. Each agent has one job and a strict contract.

The handoff pattern is the key. The orchestrator receives the request, transfers control to the classifier, then hands the Admin work to the Admin Agent. In parallel, scheduled agents can run independently, like the Idea Connector or Digest Agent, without waiting for a user request.

For sterile processing, the pattern is identical. Your orchestrator routes incoming data: sterilizer telemetry, instrument scans, and quality events. Specialist agents handle compliance checks, tray routing, predictive maintenance, quality trends, and shift briefings. Same architecture, different domain.

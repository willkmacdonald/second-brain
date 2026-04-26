# Second Brain Overview — Voiceover Script

**Total duration: ~55 seconds**
**Recommended ElevenLabs voice: "Adam" or "Antoni" (clear, professional)**
**Speed: 1.0x | Stability: 0.5 | Similarity: 0.75**

---

## INTRO (0:00 – 0:07)

The Active Second Brain. An AI-powered capture and intelligence system, built on Azure AI Foundry and the Microsoft Agent Framework.

---

## SECTION 1: What It Is (0:07 – 0:17)

Here's the problem: your brain is for thinking, not storage. Traditional note-taking fails because it forces you to organize at the moment of capture. This system flips that entirely. One tap — voice or text — and AI agents handle all the classification and filing automatically, into four smart buckets: People, Projects, Ideas, and Admin.

---

## SECTION 2: The Multi-Agent Vision (0:17 – 0:28)

The architecture is a team of specialist agents, each with a focused job. Today, two agents are live: a Classifier that routes every capture to the right bucket, and an Admin Agent that manages shopping lists by store. Three more agents are planned — Projects, Ideas, and People — each bringing proactive intelligence to their domain. All of them are persistent agents on Azure AI Foundry, powered by GPT-4o.

---

## SECTION 3: How It Works (0:28 – 0:41)

Here's the flow in practice. You capture a thought — say, "need cat litter and milk." The system transcribes it, the Classifier routes it to Admin, and the Admin Agent silently extracts those items and assigns them to the right store lists. You open the Status screen and there they are — cat litter under Pet Store, milk under Jewel. The backend is FastAPI on Azure Container Apps, with Cosmos DB for storage, SSE streaming for real-time feedback, and full observability through Application Insights.

---

## SECTION 4: What's Next (0:41 – 0:51)

Coming soon: recipe URL extraction — paste a link and get a shopping list. On-device transcription with iOS SpeechAnalyzer for zero-latency voice capture. And push notifications so you know the moment agents finish processing. Long-term, the vision expands to a Projects Agent for action tracking, an Ideas Agent for weekly check-ins, a People Agent for relationship nudges, and daily digests delivered every morning.

---

## OUTRO (0:51 – 0:55)

The Active Second Brain. Capture everything. Organize nothing.

---

## NOTES FOR ELEVENLABS

- Paste each section individually for better control over pacing
- Add a 1-second pause between sections
- Export as MP3 or WAV
- Place the audio file in `video/public/voiceover.mp3`
- Then add to the video composition:

```tsx
// In SecondBrain/index.tsx, add:
import { Audio, staticFile } from "remotion";

// Inside the component, add:
<Audio src={staticFile("voiceover.mp3")} />
```

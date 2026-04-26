# Handoff: Second Brain — Mobile (iOS)

## Overview

**Second Brain** is a personal mobile agent for one-tap thought capture. The user speaks or types a raw thought; a multi-agent backend classifies it into one of four buckets (People, Projects, Ideas, Admin), and surfaces it back as a prioritized task list, a morning briefing, or a people/project detail view.

This handoff covers the full set of mobile screens in hi-fi, plus the design tokens needed to rebuild them in a real codebase.

## About the Design Files

The files in this bundle are **design references built in HTML + React (Babel in-browser)**. They are prototypes of the intended look and behavior — not production code to lift directly. Your job is to **recreate these designs in your target codebase** (SwiftUI if you're going native iOS, React Native / Expo if cross-platform, Next.js if web-first) using that stack's established patterns.

Open `Second Brain.html` in a browser to see the live design canvas with every screen. Pan/zoom, drag artboards to reorder, click any artboard to focus it fullscreen. The Tasks screen is interactive — tap the Where / Today / Proposals segmented toggle.

## Fidelity

**High fidelity.** Colors, spacing, typography, and layout are final. Copy is representative, not final — feel free to refine voice per screen. Icon system is custom SVG; swap to SF Symbols (iOS native) or Lucide (cross-platform) as appropriate.

## Design Tokens

### Colors (dark theme only — light not designed)

```
// Surfaces
bg:        #0a0a12   // canvas / page background
surface:   #13131f   // cards, rows
surfaceHi: #1b1b2a   // active segment, elevated
hairline:  rgba(255,255,255,0.06)   // dividers
divider:   rgba(255,255,255,0.08)

// Text
text:      #f0f0f5                  // primary
textDim:   rgba(240,240,245,0.62)   // secondary
textMuted: rgba(240,240,245,0.38)   // tertiary / labels
textFaint: rgba(240,240,245,0.22)   // quaternary / metadata

// Action / accent
accent:    #7a9eff
accentDim: rgba(122,158,255,0.18)

// Status
recording: #ff5b5b   // recording indicator
ok:        #7ddca0   // healthy agents
warn:      #e6b450   // warnings
err:       #ff6b6b   // errors

// Buckets  { fg, bg, dot }
People:   fg #d7c7b4, bg rgba(215,199,180,0.10), dot #b8a387   // warm sand
Projects: fg #a9c5e8, bg rgba(169,197,232,0.10), dot #7fa5cf   // dusty blue
Ideas:    fg #c7bde0, bg rgba(199,189,224,0.10), dot #9d8fbf   // muted violet
Admin:    fg #b8d4c0, bg rgba(184,212,192,0.10), dot #88af96   // sage
```

### Typography

Three Google Fonts:

- **Instrument Serif** (italic variants) — display type. Screen titles, big moments like "What's on your mind?". Italic often.
- **Instrument Sans** — all body, labels, buttons. Weights 400/500/600/700.
- **JetBrains Mono** — metadata, timestamps, confidence %, caps labels, tabular nums.

### Type scale (observed across screens)

```
Screen title (italic serif):    36px / 400 / -0.8 tracking
Focus headline (italic serif):  32–36px / 400 / -0.7 to -0.8
Body:                           13.5–14px / 400–500 / -0.15
Secondary body:                 13px / 400 / dim color
Label (caps mono):              10px / 600 / 1.4 tracking / uppercase
Tabular metadata:               10.5–11px / mono / tabular-nums
Button/segment label:           12.5–13px / 500–600
Tab bar label:                  10.5px / 500–600
```

### Spacing

No strict scale — use multiples of 2/4. Common values: 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 26, 32.
Screen gutter: **20px** horizontal.
Card inner padding: **12–14px**.
Card-to-card gap: **8–10px**.

### Radii

```
Small chip / badge:       6–8px
Row / small card:         10–14px
Large card:               14–20px
Pills / bucket chips:     999px (fully rounded)
Mic button / circular:    half of dimension
Device frame (iPhone):    42px
```

### Borders

Hairlines are 0.5px solid rgba(255,255,255,0.06). Always prefer hairlines over 1px full opacity — this is a dark, spartan system.

## Screens

All screens are designed for iPhone at **320 × 660 logical px** (the content area inside the device frame). Safe areas: 42px top for status bar / dynamic island, 70px bottom tab bar, 28px if tab bar hidden.

### 1. Capture (hero flow — 3 states)

**Flow:** Idle → Listening → Filed

#### 1a. Idle — "What's on your mind?"
- Status bar + CapsLabel: "Thu · Feb 21" (left), "12 captured" (right)
- Huge italic serif headline: "What's on your mind?" (34px, letter-spacing -0.8, fontStyle italic) with accent-colored "?"
- Subtitle: "Don't organize it. Don't tag it. Just say it." (14px, dim)
- Three round controls at bottom, horizontally centered:
  - 54×54 square button (pencil = text mode), radius 14, surface bg
  - 86×86 round button (mic — primary), radius 43, **white on dark** fill — this is the hero affordance
  - 54×54 square button (keyboard shortcut / "⌘"), radius 14, surface bg

#### 1b. Listening
- Top row: red dot + "● Recording" CapsLabel (left), mono timer "0:07" (right)
- Live transcript area below (big italic serif, 26px): "Talk to Don about the medtech research engine — maybe swap in Stryker" with a blinking accent-colored caret
- The appended portion ("— maybe swap in Stryker") fades to textFaint with italic to show it's newest
- Bottom: animated waveform (IconWave helper, 220×36, accent color)
- Stop button: 84×84 red circle with white rounded-square icon, red glow (box-shadow 0 0 0 10px + 20px falloff)

#### 1c. Filed (post-capture confirm)
- "Voice/Text" segmented pill at top (same as idle)
- Centered column of 4 elements:
  - 100×100 circle in Projects-bucket bg, matching border, with large checkmark SVG in Projects-bucket fg
  - CapsLabel "Filed"
  - Serif headline (28px italic): "PPTX Automation"
  - Bucket chip: Projects (pill with line icon + label in bucket fg)
- "Next action" card at bottom:
  - CapsLabel "Next action"
  - Body (14px): "Draft two alternative layout strategies and compare in a test deck."

### 2. Agent Clarification (HITL)

When the classifier's confidence is low, it asks inline.

- Voice/Text segmented (Text active for this flow)
- Captured-thought card (surface bg, radius 12): `CapsLabel "You said"` + dim quoted text
- Agent bubble: accentDim bg, 2px accent left border, asks a disambiguation question with bolded entity names in their bucket's fg color
- "Pick a bucket" label + 2×2 grid:
  - Top row (candidates): People + Admin, each with their bucket bg/border/icon, full opacity
  - Bottom row (not candidates): Projects + Ideas, hairline border, 0.5 opacity
- Footer hint (mono, faint): "or reply with more context ↵"

### 3. Inbox (2 views)

#### 3a. Clean list (primary)
- Italic serif "Inbox" (36px) with `[n] items` CapsLabel on the right
- Filter pills: "All" (active, surfaceHi), then the four bucket names (hairline border, muted)
- Row: bucket line-icon at left, 2-line-clamped body, small-caps bucket name + mono timestamp below
- Rows separated by hairlines top & bottom

#### 3b. Detail / Recategorize modal
- Dimmed inbox backdrop (opacity 0.3)
- Floating card (radius 20, hairline border, drop shadow 0 20 40 rgba(0,0,0,0.5))
  - `CapsLabel "Captured"` + the full quote
  - Two-column meta: current bucket chip + confidence % (mono)
  - "Move to bucket" 4-column grid: current bucket highlighted with its bg/border/fg; others hairline only
  - Footer: thumbs up / thumbs down buttons + "Close" accent text link on the right

### 4. Daily Digest (morning briefing)

Full-bleed screen, **no tab bar**. Reaches the user as a notification / daily ritual.

- `●` + CapsLabel "Morning briefing" (accent), "06:30 CT" CapsLabel right
- Italic serif: "Thursday, Feb 21" (36px)
- Mono summary line: "12 captures · 3 filed · 1 review"
- **Today's focus** (CapsLabel in Projects.fg): numbered list `01 02 03` in mono, body text
- **Unblock this** card (surface bg, Admin-bucket border tint): "Waiting on Mike — stalled 9 days. Send a nudge?"
- Small win footer: green dot + "Closed Factory Agent Demo yesterday."

### 5. Tasks (UNIFIED — one screen, 3 views via segmented toggle)

Header: italic serif "Tasks" + `[n] to do` CapsLabel.

Segmented toggle (surface pill, 3 segments): **Where / Today / Proposals** — each with a mono count badge. Active segment = surfaceHi bg, text color, fontWeight 600.

#### View A — Where (by destination)
Groups tasks by where they get done. This is the **primary view**.

- Group header row: kind-icon (store/online/anywhere SVG) + destination name + distance chip (if store, e.g. "0.8 mi" in accentDim pill) + count + chevron
- Task row: 17×17 empty checkbox (2px accent ring + accentDim bg if priority) + task text + bucket geo-dot + "BUY" chip (if online-buyable) + mono duration
- Dashed footer card hints at GPS: "Nudge me near Target · 3 items" with animated radar glyph

**Kinds:**
- `store` → storefront-outline icon → physical store, shows distance, future GPS proximity notification
- `online` → globe-with-meridians icon → web store, future one-tap direct purchase
- `anywhere` → concentric-circle icon → location-agnostic task

#### View B — Today (priority-ordered)
- Duration summary: "~1h 20m across 4 things"
- Flat list, priority tasks have accent-ringed checkboxes
- Each row: checkbox + body + (bucket geo-dot + BUCKET caps + destination) meta + mono duration
- "Later" section below: bucket line-icon + title + destination in mono-faint

#### View C — Proposals (agent suggestions)
Italic header context: "The agent suggests these from yesterday's captures."

- Proposal card (surface bg, hairline, radius 14):
  - Top row: bucket icon + BUCKET caps + confidence % in mono
  - Body (14px)
  - "from [source]" in italic muted
  - Two buttons row: Accept (accent bg, dark text, 600 weight) + Skip (hairline outline, dim)

### 6. Status

Seven agent cards in a 2-column grid, each with traffic-light state.

**Agents to show:**
1. Orchestrator — Routes captures — ok — 180ms avg
2. Perception — Speech → text — ok — 620ms avg
3. Classifier — Bucket routing — warn — 3 errors · 1h (errCount 3)
4. Action — Executes tasks — ok — 12/19 today
5. Entity res. — Dedupes people — ok — last run 2:14 AM
6. Digest — Morning briefing — idle — runs at 6:30 AM
7. Evaluation — Self-scoring — err — failed · 22m ago (errCount 1)

**Card anatomy:**
- Surface bg, radius 12, padding 11×12
- Border tint: err=err+44, warn=warn+33, else hairline
- Header row: name (13px, 500) + 10×10 traffic dot (green/amber/red/grey, green has 3px ring glow)
- Role line: 10.5px muted (what the agent does)
- Status line: 10.5px mono — with a `⚠` prefix + colored text if errCount > 0

**Header shows overall:**
- Italic "Status" title + traffic dot + CapsLabel ("healthy" / "minor issues" / "degraded")
- Summary line: "7 agents · 5 healthy · 1 warning · 1 error"

**Recent error card** below grid (if any errs):
- Red-tinted hairline
- Dot + `CapsLabel "Last error · 22m ago"`
- Body describing the failure
- Accent "Retry now →" action

### 7. Settings

Grouped iOS-style list. Italic serif title "Settings".

**Sections (each with CapsLabel header + rounded surface card, hairline rows):**
- **Account**: API key (••••••tz7), Signed in as (will)
- **Capture**: On-device speech (On), Haptics (Medium), Digest time (6:30 AM)
- **Agents**: Evaluation report (Sunday 7 PM), Entity resolution (Nightly 2 AM)

Each row: title flex + mono dim value + right chevron.

## Tab Bar

4 tabs, fixed bottom, 70px tall, dark translucent bg (rgba(10,10,18,0.85) + backdrop-filter blur 20px), hairline top border.

| Key     | Label   | Icon     | Badge?          |
|---------|---------|----------|-----------------|
| capture | Capture | Mic      | —               |
| inbox   | Inbox   | Inbox    | accent count    |
| tasks   | Tasks   | Checkbox | —               |
| status  | Status  | Spark    | red if err > 0  |

Active: text color, 600 weight, stroke 1.8. Inactive: textMuted, 500 weight, stroke 1.4.

## Interactions & Behavior

### Capture flow
1. Tap mic on Idle screen → haptic → transition to Listening (fade ~200ms)
2. Live speech-to-text streams into the transcript area as user speaks
3. Tap stop (or 2s of silence) → optimistic UI flashes Filed screen with predicted bucket
4. If confidence < threshold (e.g. 0.7), skip Filed and route to HITL Clarification instead

### HITL Clarification
- Tapping a candidate bucket files the capture and animates back to Capture idle
- "or reply with more context ↵" opens text input below the bubble

### Inbox
- Tap a row → opens Detail modal (slide up, backdrop dims)
- Swipe row right → quick file to predicted bucket
- Swipe row left → delete

### Tasks
- Segmented toggle is client-state only — same task pool, different lens
- Tap checkbox → task strikes through + opacity fade, then collapses after 800ms
- On Where view, "Nudge me near Target" chip taps through to notification settings
- BUY chip on an online task → platform's web checkout (Amazon deep link, etc.)
- GPS proximity: when `dist < 0.5 mi`, fire local notification "3 tasks at Target"

### Digest
- Delivered as push notification at user-configured time (Capture tab badge doesn't increment for digests)
- Tapping the push opens the full digest full-screen (no tab bar)
- Swipe down to dismiss

### Status
- Tap any agent card → drill-down (not designed yet) showing recent traces, retry button, sample classifications
- Tap "Retry now →" on recent error card → kicks off retry, shows loading state inline

## State Model (rough)

```typescript
type Bucket = 'People' | 'Projects' | 'Ideas' | 'Admin';

type Capture = {
  id: string;
  raw: string;            // transcript
  createdAt: Date;
  bucket: Bucket | null;  // null until classified
  confidence: number;     // 0..1
  entities: { name: string; bucket: Bucket }[];
};

type Task = {
  id: string;
  title: string;
  bucket: Bucket;
  sourceCaptureId: string;
  destination?: { kind: 'store' | 'online' | 'anywhere'; name: string; dist?: string; buy?: boolean; };
  estMinutes: number;
  due?: Date;
  priority: boolean;
  today: boolean;
  proposal?: { from: string; conf: number };  // present on agent-proposed tasks
  completedAt?: Date;
};

type AgentStatus = {
  name: string;
  role: string;
  state: 'ok' | 'warn' | 'err' | 'idle';
  stat: string;           // human-readable latest stat
  errCount?: number;
};
```

## Files in this bundle

- `Second Brain.html` — top-level HTML, wires everything up on the design canvas
- `screens/tokens.jsx` — color tokens (`SB`) and typography systems (`TYPE`)
- `screens/icons.jsx` — SVG icon set (mic, pencil, inbox, check, spark, wave, chevron) and 3 bucket-icon approaches (Line, Geo, Mark). **Prefer SF Symbols (iOS) or Lucide (web) in your real impl.**
- `screens/shell.jsx` — `SBFrame` device wrapper (status bar, tab bar, home indicator) + `SBTabBar`, `BucketChip`, `CapsLabel` primitives
- `screens/capture.jsx` — CaptureA_Idle, CaptureB_Listening, CaptureC_Serif, CaptureD_Confirm
- `screens/inbox.jsx` — InboxA_List, InboxB_Timeline, InboxC_Detail
- `screens/other.jsx` — DigestA_Briefing, HITL_Clarify, StatusA, SettingsA, plus deprecated Tasks A/B/C
- `screens/tasks-unified.jsx` — **the current Tasks screen** — TasksUnified with segmented view toggle
- `lib/design-canvas.jsx` — canvas viewer (tool, not product code — ignore for implementation)

## Notes for implementation

- **This is a dark-first product.** Don't assume a light theme exists — design for it explicitly if you add it.
- **Typography is the brand.** Instrument Serif italic headlines are load-bearing emotional moments. Don't let a well-meaning refactor swap it for system-ui.
- **Buckets are a core concept.** Always surface them with color + icon + name, never just color or just name. Colors are intentionally muted — resist juicing them up.
- **Agent transparency matters.** The Status screen is not a dev tool — it's a user-facing trust surface. Keep it calm and legible.
- **The mic is sacred.** The idle-screen 86×86 mic button is the emotional center of the product. Give it room; don't clutter around it.

# Phase 2: Expo App Shell - Context

**Gathered:** 2026-02-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Mobile capture surface — Expo app with four capture buttons (Voice, Text, Photo, Video) and a text input flow that sends thoughts to the deployed FastAPI backend. Only Text capture is functional; other buttons are visible but disabled. No navigation, settings, folders, or tags.

</domain>

<decisions>
## Implementation Decisions

### Main screen layout
- Vertical stack of four full-width buttons
- Each button has icon + label (mic, keyboard, camera, video icons)
- Dark mode styling (dark background, light buttons)
- No header, no app name, no branding — just the four buttons filling the screen
- Button order: Voice, Text, Photo, Video

### Text capture flow
- Tapping Text navigates to a full-screen input view with Back button, large text area, and Send button
- Keyboard auto-opens on the text input screen (auto-focus)
- Send button is disabled when the text field is empty
- After sending: brief "Sent" toast, auto-navigate back to main screen
- On error: toast at the bottom ("Couldn't send — check connection"), user stays on input screen with text preserved

### Backend connectivity
- Real connection to deployed Azure Container Apps backend (not mocked)
- POST to the AG-UI endpoint with API key in Authorization header
- Fire-and-forget: confirm send via toast, don't display the agent's SSE response (that's Phase 4)
- Backend URL and API key stored in .env file using EXPO_PUBLIC_ prefix, baked in at build time
- Backend is already deployed on Azure Container Apps from Phase 1

### Disabled buttons
- Voice, Photo, Video buttons are visually dimmed (faded/grayed appearance)
- Tapping a disabled button shows a generic "Coming soon" toast
- No feature-specific toast text — same message for all three

### Claude's Discretion
- Exact icon choices for each button
- Toast library/implementation
- Text area placeholder text
- Spacing and typography details
- Loading spinner/indicator while sending

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-expo-app-shell*
*Context gathered: 2026-02-21*

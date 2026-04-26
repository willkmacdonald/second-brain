// Capture screen — the hero moment. Four variations.
// A: System — classic, breath. Large mic, just a caption.
// B: Mono — technical, ready/listening state with transcript rail.
// C: Serif — editorial, quiet: "what's on your mind" as serif.
// D: Post-capture confirm — "Filed → Projects"

const CaptureA_Idle = ({ typefaces = TYPE.system }) => (
  <SBFrame typefaces={typefaces} activeTab="capture">
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '6px 20px 0' }}>
      {/* Voice/Text segmented */}
      <div style={{
        marginTop: 14, padding: 3, borderRadius: 10,
        background: SB.surface, display: 'flex', gap: 2,
      }}>
        {['Voice', 'Text'].map((l, i) => (
          <div key={l} style={{
            flex: 1, padding: '8px 0', textAlign: 'center',
            borderRadius: 8,
            background: i === 0 ? SB.surfaceHi : 'transparent',
            color: i === 0 ? SB.text : SB.textMuted,
            fontSize: 13, fontWeight: 600, letterSpacing: -0.15,
            fontFamily: typefaces.body,
          }}>{l}</div>
        ))}
      </div>

      {/* Mic zone */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 32 }}>
        <div style={{
          width: 148, height: 148, borderRadius: 74,
          background: 'radial-gradient(circle at 35% 30%, #24243a, #13131f 70%)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          position: 'relative',
          boxShadow: 'inset 0 0 0 0.5px rgba(255,255,255,0.08)',
        }}>
          <div style={{
            position: 'absolute', inset: -18, borderRadius: 100,
            border: `1px solid ${SB.hairline}`,
          }} />
          <IconMic size={46} color={SB.text} stroke={1.2} />
        </div>
        <div style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ fontSize: 15, color: SB.text, letterSpacing: -0.2, fontFamily: typefaces.body }}>
            Tap to capture
          </div>
          <CapsLabel typefaces={typefaces} size={10}>One thought · one tap</CapsLabel>
        </div>
      </div>
    </div>
  </SBFrame>
);

const CaptureB_Listening = ({ typefaces = TYPE.mono }) => (
  <SBFrame typefaces={typefaces} activeTab="capture">
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '6px 20px 0' }}>
      <div style={{ marginTop: 14, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <CapsLabel typefaces={typefaces} color={SB.recording}>● Recording</CapsLabel>
        <span style={{ fontFamily: typefaces.mono, fontSize: 13, color: SB.textDim, fontVariantNumeric: 'tabular-nums' }}>0:07</span>
      </div>

      {/* Live transcript */}
      <div style={{
        marginTop: 18, padding: '16px 2px',
        minHeight: 140,
      }}>
        <div style={{
          fontFamily: typefaces.display, fontSize: 26, lineHeight: 1.3,
          color: SB.text, letterSpacing: -0.4, fontWeight: 400,
        }}>
          Talk to Don about the medtech research engine&nbsp;
          <span style={{ color: SB.textFaint, fontStyle: 'italic' }}>— maybe swap in Stryker</span>
          <span style={{ display: 'inline-block', width: 2, height: 22, background: SB.accent, marginLeft: 3, verticalAlign: -3 }} />
        </div>
      </div>

      <div style={{ flex: 1 }} />

      {/* Waveform + stop */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20, marginBottom: 18 }}>
        <IconWave w={220} h={36} color={SB.accent} active />
        <div style={{
          width: 84, height: 84, borderRadius: 42,
          background: SB.recording,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          boxShadow: `0 0 0 10px ${SB.recording}22, 0 0 0 20px ${SB.recording}11`,
        }}>
          <div style={{ width: 24, height: 24, borderRadius: 5, background: '#fff' }} />
        </div>
      </div>
    </div>
  </SBFrame>
);

const CaptureC_Serif = ({ typefaces = TYPE.serif }) => (
  <SBFrame typefaces={typefaces} activeTab="capture">
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '6px 22px 0' }}>
      <div style={{ marginTop: 14, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <CapsLabel typefaces={typefaces}>Thu · Feb 21</CapsLabel>
        <CapsLabel typefaces={typefaces}>12 captured</CapsLabel>
      </div>

      <div style={{ marginTop: 44, display: 'flex', flexDirection: 'column', gap: 6 }}>
        <div style={{
          fontFamily: typefaces.display, fontSize: 34, lineHeight: 1.1,
          color: SB.text, letterSpacing: -0.8, fontWeight: 400,
          fontStyle: 'italic',
        }}>
          What's on your mind<span style={{ color: SB.accent }}>?</span>
        </div>
        <div style={{ color: SB.textDim, fontSize: 14, marginTop: 6, lineHeight: 1.4 }}>
          Don't organize it. Don't tag it. Just say it.
        </div>
      </div>

      <div style={{ flex: 1 }} />

      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 16,
        marginBottom: 40,
      }}>
        <div style={{
          width: 54, height: 54, borderRadius: 14, background: SB.surface,
          border: `0.5px solid ${SB.hairline}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <IconPencil size={22} color={SB.textDim} />
        </div>
        <div style={{
          width: 86, height: 86, borderRadius: 43,
          background: SB.text, color: SB.bg,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <IconMic size={34} color={SB.bg} stroke={1.8} />
        </div>
        <div style={{
          width: 54, height: 54, borderRadius: 14, background: SB.surface,
          border: `0.5px solid ${SB.hairline}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: SB.textDim, fontSize: 20,
        }}>⌘</div>
      </div>
    </div>
  </SBFrame>
);

const CaptureD_Confirm = ({ typefaces = TYPE.system }) => (
  <SBFrame typefaces={typefaces} activeTab="capture">
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '6px 20px 0' }}>
      <div style={{ marginTop: 14, padding: 3, borderRadius: 10, background: SB.surface, display: 'flex', gap: 2 }}>
        {['Voice', 'Text'].map((l, i) => (
          <div key={l} style={{
            flex: 1, padding: '8px 0', textAlign: 'center', borderRadius: 8,
            background: i === 0 ? SB.surfaceHi : 'transparent',
            color: i === 0 ? SB.text : SB.textMuted,
            fontSize: 13, fontWeight: 600, fontFamily: typefaces.body,
          }}>{l}</div>
        ))}
      </div>

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 24 }}>
        {/* Checkmark orb */}
        <div style={{
          width: 100, height: 100, borderRadius: 50,
          background: SB.buckets.Projects.bg,
          border: `1px solid ${SB.buckets.Projects.dot}55`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <svg width="42" height="42" viewBox="0 0 42 42" fill="none">
            <path d="M12 22l7 7 12-14" stroke={SB.buckets.Projects.fg} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>

        <div style={{ textAlign: 'center', display: 'flex', flexDirection: 'column', gap: 10, alignItems: 'center' }}>
          <CapsLabel typefaces={typefaces}>Filed</CapsLabel>
          <div style={{
            fontFamily: typefaces.display, fontSize: 28, fontWeight: 400,
            color: SB.text, letterSpacing: -0.5,
          }}>PPTX Automation</div>
          <BucketChip bucket="Projects" typefaces={typefaces} size="md" />
        </div>

        {/* Next action */}
        <div style={{
          marginTop: 6, padding: '14px 16px',
          background: SB.surface, borderRadius: 14,
          border: `0.5px solid ${SB.hairline}`,
          width: '100%', maxWidth: 260,
        }}>
          <CapsLabel typefaces={typefaces} size={9}>Next action</CapsLabel>
          <div style={{ marginTop: 6, fontSize: 14, lineHeight: 1.45, color: SB.text, letterSpacing: -0.15 }}>
            Draft two alternative layout strategies and compare in a test deck.
          </div>
        </div>
      </div>
    </div>
  </SBFrame>
);

Object.assign(window, { CaptureA_Idle, CaptureB_Listening, CaptureC_Serif, CaptureD_Confirm });

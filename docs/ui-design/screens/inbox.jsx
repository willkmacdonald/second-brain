// Inbox screen — three variations.
// A: Clean list with muted bucket chips
// B: Timeline / grouped by time with monogram marks
// C: Detail modal with bucket recategorization

const sampleItems = [
  { t: '2m', text: 'Talk to Don about the medtech research engine — maybe swap in Stryker', bucket: 'Projects', conf: 0.85 },
  { t: '18m', text: "Maybe rethink the layout approach for pptx", bucket: 'Projects', conf: 0.78 },
  { t: '1h', text: "Don's birthday is March 12", bucket: 'People', conf: 0.92 },
  { t: '3h', text: "Use DSPy to learn slide layouts from examples", bucket: 'Ideas', conf: 0.81 },
  { t: '4h', text: "Renew car registration by March 15", bucket: 'Admin', conf: 0.94 },
  { t: 'Yest', text: "Mike mentioned the Stryker deal is pushed to Q3", bucket: 'People', conf: 0.72 },
  { t: 'Yest', text: "What if the orchestrator could learn from corrections?", bucket: 'Ideas', conf: 0.68 },
];

const InboxA_List = ({ typefaces = TYPE.system, iconStyle = 'line' }) => (
  <SBFrame typefaces={typefaces} activeTab="inbox">
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '14px 0 0' }}>
      <div style={{ padding: '0 20px 12px', display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <div style={{ fontFamily: typefaces.display, fontSize: 36, fontWeight: 400, letterSpacing: -0.8, color: SB.text, fontStyle: 'italic' }}>Inbox</div>
        <CapsLabel typefaces={typefaces}>{sampleItems.length} items</CapsLabel>
      </div>

      {/* Filter row */}
      <div style={{ padding: '0 20px 14px', display: 'flex', gap: 6 }}>
        <div style={{
          padding: '5px 10px', borderRadius: 8, background: SB.surfaceHi,
          color: SB.text, fontSize: 12, fontWeight: 500, fontFamily: typefaces.body,
        }}>All</div>
        {['People','Projects','Ideas','Admin'].map(b => (
          <div key={b} style={{
            padding: '5px 10px', borderRadius: 8,
            border: `0.5px solid ${SB.hairline}`,
            color: SB.textMuted, fontSize: 12, fontWeight: 500, fontFamily: typefaces.body,
          }}>{b}</div>
        ))}
      </div>

      <div style={{ flex: 1, overflow: 'hidden' }}>
        {sampleItems.map((it, i) => (
          <div key={i} style={{
            padding: '12px 20px',
            borderTop: i === 0 ? `0.5px solid ${SB.hairline}` : 'none',
            borderBottom: `0.5px solid ${SB.hairline}`,
            display: 'flex', gap: 12,
          }}>
            <div style={{ paddingTop: 3 }}>
              <BucketIconLine bucket={it.bucket} size={14} color={SB.buckets[it.bucket].dot} />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{
                fontSize: 13.5, lineHeight: 1.4, color: SB.text, letterSpacing: -0.15,
                overflow: 'hidden', textOverflow: 'ellipsis',
                display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
              }}>{it.text}</div>
              <div style={{ marginTop: 5, display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ fontSize: 10.5, fontFamily: typefaces.mono, color: SB.buckets[it.bucket].fg, letterSpacing: 0.2 }}>
                  {it.bucket.toLowerCase()}
                </span>
                <span style={{ fontSize: 10.5, color: SB.textFaint }}>·</span>
                <span style={{ fontSize: 10.5, fontFamily: typefaces.mono, color: SB.textMuted, fontVariantNumeric: 'tabular-nums' }}>
                  {it.t}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  </SBFrame>
);

const InboxB_Timeline = ({ typefaces = TYPE.mono }) => (
  <SBFrame typefaces={typefaces} activeTab="inbox">
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '14px 0 0' }}>
      <div style={{ padding: '0 20px 16px' }}>
        <CapsLabel typefaces={typefaces}>Today · Thu Feb 21</CapsLabel>
        <div style={{ fontFamily: typefaces.display, fontSize: 36, fontWeight: 400, letterSpacing: -0.8, color: SB.text, marginTop: 4, fontStyle: 'italic' }}>
          Seven captures.
        </div>
      </div>

      <div style={{ flex: 1, overflow: 'hidden', padding: '0 20px' }}>
        {sampleItems.slice(0, 6).map((it, i) => (
          <div key={i} style={{
            display: 'grid', gridTemplateColumns: '42px 1fr', gap: 10,
            padding: '10px 0', position: 'relative',
          }}>
            <div style={{
              fontFamily: typefaces.mono, fontSize: 10.5, color: SB.textMuted,
              paddingTop: 4, fontVariantNumeric: 'tabular-nums',
            }}>
              {it.t}
            </div>
            <div style={{
              background: SB.surface, borderRadius: 12, padding: '10px 12px',
              border: `0.5px solid ${SB.hairline}`,
              display: 'flex', flexDirection: 'column', gap: 6,
            }}>
              <div style={{ fontSize: 13, color: SB.text, lineHeight: 1.4, letterSpacing: -0.15 }}>
                {it.text}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <BucketIconGeo bucket={it.bucket} size={8} color={SB.buckets[it.bucket].dot} />
                <span style={{ fontSize: 10, color: SB.buckets[it.bucket].fg, fontFamily: typefaces.mono, letterSpacing: 0.3 }}>
                  {it.bucket.toUpperCase()}
                </span>
                <span style={{ fontSize: 10, color: SB.textFaint, fontFamily: typefaces.mono }}>
                  · {(it.conf * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  </SBFrame>
);

const InboxC_Detail = ({ typefaces = TYPE.system }) => (
  <SBFrame typefaces={typefaces} activeTab="inbox" bg={SB.bg}>
    {/* Backdrop inbox (dimmed) */}
    <div style={{ flex: 1, position: 'relative', opacity: 0.3, padding: '14px 20px 0', overflow: 'hidden' }}>
      <div style={{ fontFamily: typefaces.display, fontSize: 28, fontWeight: 600, color: SB.text }}>Inbox</div>
      {sampleItems.slice(0,3).map((it,i) => (
        <div key={i} style={{ padding: '14px 0', borderBottom: `0.5px solid ${SB.hairline}` }}>
          <div style={{ fontSize: 13, color: SB.text }}>{it.text}</div>
        </div>
      ))}
    </div>

    {/* Modal card */}
    <div style={{
      position: 'absolute', left: 14, right: 14, top: 120, zIndex: 30,
      background: SB.surface, borderRadius: 20,
      border: `0.5px solid ${SB.hairline}`, padding: 18,
      boxShadow: '0 20px 40px rgba(0,0,0,0.5)',
    }}>
      <CapsLabel typefaces={typefaces}>Captured</CapsLabel>
      <div style={{ marginTop: 6, fontSize: 15, color: SB.text, lineHeight: 1.45, letterSpacing: -0.2 }}>
        Talk to Don about the medtech research engine — maybe swap in Stryker
      </div>

      <div style={{ marginTop: 16, display: 'flex', gap: 18 }}>
        <div style={{ flex: 1 }}>
          <CapsLabel typefaces={typefaces}>Bucket</CapsLabel>
          <div style={{ marginTop: 4 }}><BucketChip bucket="Projects" typefaces={typefaces} /></div>
        </div>
        <div style={{ flex: 1 }}>
          <CapsLabel typefaces={typefaces}>Confidence</CapsLabel>
          <div style={{ marginTop: 4, fontFamily: typefaces.mono, fontSize: 14, color: SB.text, fontVariantNumeric: 'tabular-nums' }}>85%</div>
        </div>
      </div>

      <div style={{ marginTop: 16 }}>
        <CapsLabel typefaces={typefaces}>Move to bucket</CapsLabel>
        <div style={{ marginTop: 8, display: 'flex', gap: 6 }}>
          {['People','Projects','Ideas','Admin'].map(b => {
            const isCurrent = b === 'Projects';
            return (
              <div key={b} style={{
                flex: 1, textAlign: 'center', padding: '8px 0', borderRadius: 9,
                background: isCurrent ? SB.buckets[b].bg : 'transparent',
                border: `0.5px solid ${isCurrent ? SB.buckets[b].dot + '66' : SB.hairline}`,
                color: isCurrent ? SB.buckets[b].fg : SB.textDim,
                fontSize: 11.5, fontWeight: 500, fontFamily: typefaces.body,
              }}>{b}</div>
            );
          })}
        </div>
      </div>

      <div style={{ marginTop: 16, display: 'flex', gap: 10, alignItems: 'center' }}>
        <div style={{
          width: 36, height: 32, borderRadius: 9, background: SB.surfaceHi,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 14,
        }}>👍</div>
        <div style={{
          width: 36, height: 32, borderRadius: 9, background: SB.surfaceHi,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 14,
        }}>👎</div>
        <div style={{ flex: 1 }} />
        <div style={{ fontSize: 12, color: SB.accent, fontWeight: 600, fontFamily: typefaces.body }}>Close</div>
      </div>
    </div>
  </SBFrame>
);

Object.assign(window, { InboxA_List, InboxB_Timeline, InboxC_Detail });

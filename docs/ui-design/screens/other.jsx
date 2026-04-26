// Status A — 7 agent cards in a grid, each with traffic-light state + error count

const StatusA = ({ typefaces = TYPE.serif }) => {
  const agents = [
    { n: 'Orchestrator',  role: 'Routes captures', status: 'ok',   stat: '180ms avg' },
    { n: 'Perception',    role: 'Speech → text',    status: 'ok',   stat: '620ms avg' },
    { n: 'Classifier',    role: 'Bucket routing',   status: 'warn', stat: '3 errors · 1h',  errCount: 3 },
    { n: 'Action',        role: 'Executes tasks',   status: 'ok',   stat: '12/19 today' },
    { n: 'Entity res.',   role: 'Dedupes people',   status: 'ok',   stat: 'last run 2:14 AM' },
    { n: 'Digest',        role: 'Morning briefing', status: 'idle', stat: 'runs at 6:30 AM' },
    { n: 'Evaluation',    role: 'Self-scoring',     status: 'err',  stat: 'failed · 22m ago', errCount: 1 },
  ];

  const dot = (status) => {
    const c = { ok: SB.ok, warn: SB.warn, err: SB.err, idle: SB.textFaint }[status];
    return (
      <div style={{ position: 'relative', width: 10, height: 10 }}>
        <div style={{ position:'absolute', inset:0, borderRadius:5, background:c, boxShadow: status==='ok'?`0 0 0 3px ${c}22`:'none' }}/>
      </div>
    );
  };

  const overall = agents.some(a => a.status === 'err') ? 'degraded' : agents.some(a=>a.status==='warn') ? 'minor issues' : 'healthy';
  const overallColor = overall === 'healthy' ? SB.ok : overall === 'degraded' ? SB.err : SB.warn;

  return (
    <SBFrame typefaces={typefaces} activeTab="status">
      <div style={{ flex: 1, padding: '14px 20px 0', overflow: 'hidden' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
          <div style={{ fontFamily: typefaces.display, fontSize: 36, fontWeight: 400, color: SB.text, letterSpacing: -0.8, fontStyle: 'italic' }}>Status</div>
          <div style={{ display:'flex', alignItems:'center', gap:6 }}>
            {dot(overall==='healthy'?'ok':overall==='degraded'?'err':'warn')}
            <CapsLabel typefaces={typefaces} color={overallColor}>{overall}</CapsLabel>
          </div>
        </div>

        {/* Summary line */}
        <div style={{ marginTop: 4, fontSize: 12, color: SB.textDim, fontFamily: typefaces.body, lineHeight: 1.4 }}>
          7 agents · 5 healthy · 1 warning · 1 error
        </div>

        {/* 7 agent cards in 2-col grid */}
        <div style={{ marginTop: 16, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          {agents.map((a, i) => {
            const c = { ok: SB.ok, warn: SB.warn, err: SB.err, idle: SB.textFaint }[a.status];
            return (
              <div key={i} style={{
                background: SB.surface, borderRadius: 12, padding: '11px 12px',
                border: `0.5px solid ${a.status === 'err' ? SB.err + '44' : a.status === 'warn' ? SB.warn + '33' : SB.hairline}`,
                position: 'relative', minHeight: 74,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: 12.5, color: SB.text, fontWeight: 500, letterSpacing: -0.15, fontFamily: typefaces.body }}>{a.n}</span>
                  {dot(a.status)}
                </div>
                <div style={{ marginTop: 4, fontSize: 10.5, color: SB.textMuted, fontFamily: typefaces.body, lineHeight: 1.35 }}>
                  {a.role}
                </div>
                <div style={{ marginTop: 6, fontSize: 10.5, fontFamily: typefaces.mono, color: a.errCount ? c : SB.textDim, letterSpacing: 0.1, fontVariantNumeric: 'tabular-nums' }}>
                  {a.errCount ? `⚠ ${a.stat}` : a.stat}
                </div>
              </div>
            );
          })}
        </div>

        {/* Recent error */}
        <div style={{ marginTop: 14, padding: '12px 14px', background: SB.surface, borderRadius: 12, border: `0.5px solid ${SB.err}33` }}>
          <div style={{ display:'flex', alignItems:'center', gap:8 }}>
            {dot('err')}
            <CapsLabel typefaces={typefaces} color={SB.err}>Last error · 22m ago</CapsLabel>
          </div>
          <div style={{ marginTop: 6, fontSize: 12.5, color: SB.text, lineHeight: 1.4, letterSpacing: -0.1 }}>
            Evaluation agent timed out scoring yesterday's classifications.
          </div>
          <div style={{ marginTop: 6, fontSize: 11, color: SB.accent, fontWeight: 500, fontFamily: typefaces.body }}>Retry now →</div>
        </div>
      </div>
    </SBFrame>
  );
};

// ─── Settings (unchanged, kept here for colocation) ─────────────
const SettingsA = ({ typefaces = TYPE.serif }) => (
  <SBFrame typefaces={typefaces} activeTab="status">
    <div style={{ flex: 1, padding: '14px 0 0', overflow: 'hidden' }}>
      <div style={{ padding: '0 20px 14px' }}>
        <div style={{ fontFamily: typefaces.display, fontSize: 36, fontWeight: 400, color: SB.text, letterSpacing: -0.8, fontStyle: 'italic' }}>Settings</div>
      </div>

      {[
        { h: 'Account', rows: [{t:'API key', d:'••••••tz7'},{t:'Signed in as', d:'will'}] },
        { h: 'Capture', rows: [{t:'On-device speech', d:'On'},{t:'Haptics', d:'Medium'},{t:'Digest time', d:'6:30 AM'}] },
        { h: 'Agents', rows: [{t:'Evaluation report', d:'Sunday 7 PM'},{t:'Entity resolution', d:'Nightly 2 AM'}] },
      ].map((sec, si) => (
        <div key={si} style={{ marginTop: si === 0 ? 0 : 18 }}>
          <div style={{ padding: '0 20px 6px' }}><CapsLabel typefaces={typefaces}>{sec.h}</CapsLabel></div>
          <div style={{ margin: '0 16px', background: SB.surface, borderRadius: 14, overflow: 'hidden', border: `0.5px solid ${SB.hairline}` }}>
            {sec.rows.map((r, i) => (
              <div key={i} style={{
                padding: '13px 14px', display: 'flex', alignItems: 'center',
                borderTop: i === 0 ? 'none' : `0.5px solid ${SB.hairline}`,
              }}>
                <span style={{ flex: 1, fontSize: 14, color: SB.text, letterSpacing: -0.15 }}>{r.t}</span>
                <span style={{ fontSize: 13, color: SB.textDim, marginRight: 8, fontFamily: typefaces.mono }}>{r.d}</span>
                <IconChevron size={11} color={SB.textFaint} />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  </SBFrame>
);

// ─── Daily Digest — morning briefing ─────────────
const DigestA_Briefing = ({ typefaces = TYPE.serif }) => (
  <SBFrame typefaces={typefaces} activeTab="inbox" showTabBar={false}>
    <div style={{ flex: 1, padding: '16px 22px 0', overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <CapsLabel typefaces={typefaces} color={SB.accent}>● Morning briefing</CapsLabel>
        <CapsLabel typefaces={typefaces}>06:30 CT</CapsLabel>
      </div>
      <div style={{ marginTop: 6, fontFamily: typefaces.display, fontSize: 36, fontWeight: 400, color: SB.text, letterSpacing: -0.8, fontStyle: 'italic' }}>
        Thursday, Feb 21
      </div>
      <div style={{ fontSize: 12, color: SB.textDim, marginTop: 2, fontFamily: typefaces.mono }}>
        12 captures · 3 filed · 1 review
      </div>

      <div style={{ marginTop: 22 }}>
        <CapsLabel typefaces={typefaces} color={SB.buckets.Projects.fg}>Today's focus</CapsLabel>
        <ol style={{ margin: '10px 0 0', padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 8 }}>
          {[
            'Draft two PPTX layout strategies, compare in test deck',
            'Email Sarah re: Q3 Stryker timeline',
            'Renew car registration at ilsos.gov',
          ].map((t, i) => (
            <li key={i} style={{ display: 'flex', gap: 10, alignItems: 'baseline' }}>
              <span style={{ fontFamily: typefaces.mono, fontSize: 11, color: SB.textFaint, width: 14 }}>0{i+1}</span>
              <span style={{ fontSize: 13.5, color: SB.text, lineHeight: 1.45, letterSpacing: -0.15 }}>{t}</span>
            </li>
          ))}
        </ol>
      </div>

      <div style={{ marginTop: 22, padding: '14px 14px', background: SB.surface, borderRadius: 14, border: `0.5px solid ${SB.buckets.Admin.dot}33` }}>
        <CapsLabel typefaces={typefaces} color={SB.buckets.Admin.fg}>Unblock this</CapsLabel>
        <div style={{ marginTop: 6, fontSize: 13.5, color: SB.text, lineHeight: 1.4 }}>
          "Waiting on Mike" — stalled 9 days. Send a nudge?
        </div>
      </div>

      <div style={{ marginTop: 14, display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ width: 6, height: 6, borderRadius: 3, background: SB.ok }} />
        <div style={{ fontSize: 12, color: SB.textDim, lineHeight: 1.4, fontFamily: typefaces.body }}>
          Closed <span style={{ color: SB.text }}>Factory Agent Demo</span> yesterday.
        </div>
      </div>
    </div>
  </SBFrame>
);

// ─── HITL clarification ─────────────
const HITL_Clarify = ({ typefaces = TYPE.serif }) => (
  <SBFrame typefaces={typefaces} activeTab="capture">
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '6px 20px 0' }}>
      <div style={{ marginTop: 14, padding: 3, borderRadius: 10, background: SB.surface, display: 'flex', gap: 2 }}>
        {['Voice', 'Text'].map((l, i) => (
          <div key={l} style={{
            flex: 1, padding: '8px 0', textAlign: 'center', borderRadius: 8,
            background: i === 1 ? SB.surfaceHi : 'transparent',
            color: i === 1 ? SB.text : SB.textMuted,
            fontSize: 13, fontWeight: 600, fontFamily: typefaces.body,
          }}>{l}</div>
        ))}
      </div>

      <div style={{ marginTop: 18, padding: '10px 12px', background: SB.surface, borderRadius: 12, border: `0.5px solid ${SB.hairline}` }}>
        <CapsLabel typefaces={typefaces}>You said</CapsLabel>
        <div style={{ fontSize: 13, color: SB.textDim, marginTop: 4, lineHeight: 1.4 }}>
          "Follow up with Mike about the deadline"
        </div>
      </div>

      <div style={{
        marginTop: 14, padding: '14px 14px',
        background: SB.accentDim, borderRadius: 14,
        borderLeft: `2px solid ${SB.accent}`,
      }}>
        <div style={{ fontSize: 14, color: SB.text, lineHeight: 1.45, letterSpacing: -0.15 }}>
          That mentions Mike and a deadline. Is this a follow-up with{' '}
          <span style={{ color: SB.buckets.People.fg, fontWeight: 600 }}>Mike</span>{' '}
          (People) or a task you need to do (Admin)?
        </div>
      </div>

      <div style={{ marginTop: 18 }}>
        <CapsLabel typefaces={typefaces}>Pick a bucket</CapsLabel>
        <div style={{ marginTop: 10, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          {['People','Admin'].map(b => (
            <div key={b} style={{
              padding: '12px 10px', borderRadius: 12,
              background: SB.buckets[b].bg,
              border: `0.5px solid ${SB.buckets[b].dot}66`,
              display: 'flex', alignItems: 'center', gap: 8,
            }}>
              <BucketIconLine bucket={b} size={16} color={SB.buckets[b].fg} />
              <span style={{ fontSize: 13, fontWeight: 600, color: SB.buckets[b].fg, letterSpacing: -0.15 }}>{b}</span>
            </div>
          ))}
          {['Projects','Ideas'].map(b => (
            <div key={b} style={{
              padding: '12px 10px', borderRadius: 12,
              border: `0.5px solid ${SB.hairline}`,
              display: 'flex', alignItems: 'center', gap: 8,
              opacity: 0.5,
            }}>
              <BucketIconLine bucket={b} size={16} color={SB.textMuted} />
              <span style={{ fontSize: 13, fontWeight: 500, color: SB.textMuted, letterSpacing: -0.15 }}>{b}</span>
            </div>
          ))}
        </div>
      </div>

      <div style={{ flex: 1 }} />
      <div style={{ textAlign: 'center', marginBottom: 14, fontSize: 11, color: SB.textFaint, fontFamily: typefaces.mono }}>
        or reply with more context ↵
      </div>
    </div>
  </SBFrame>
);

// ─── Tasks — three directions ────────────────────────────────────

// A: By destination — physical stores, online, anywhere (+ GPS/buy hints)
const TasksA_ByBucket = ({ typefaces = TYPE.serif }) => {
  const sections = [
    { name: 'Target', kind: 'store', dist: '0.8 mi', items: [
      { t: 'Pick up printer ink', bucket: 'Admin' },
      { t: 'Birthday card for Don', bucket: 'People' },
      { t: 'New chisel set', bucket: 'Ideas' },
    ]},
    { name: 'Home Depot', kind: 'store', dist: '2.1 mi', items: [
      { t: 'Oak boards (2× 6ft)', bucket: 'Ideas' },
    ]},
    { name: 'amazon.com', kind: 'online', items: [
      { t: 'Return the blue jacket', bucket: 'Admin' },
      { t: 'Reorder coffee beans', bucket: 'Admin', buy: true },
    ]},
    { name: 'ilsos.gov', kind: 'online', items: [
      { t: 'Renew car registration · due Mar 15', bucket: 'Admin' },
    ]},
    { name: 'Anywhere', kind: 'anywhere', items: [
      { t: 'Reply to Sarah re: Q3 timeline', bucket: 'People' },
      { t: 'Draft PPTX layout strategies', bucket: 'Projects' },
    ]},
  ];

  const kindIcon = (kind) => {
    if (kind === 'store') return (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
        <path d="M2 6l1-3h10l1 3M2.5 6v7.5h11V6M6 9h4" stroke={SB.textDim} strokeWidth="1.2" strokeLinejoin="round" strokeLinecap="round"/>
      </svg>
    );
    if (kind === 'online') return (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
        <circle cx="8" cy="8" r="5.5" stroke={SB.textDim} strokeWidth="1.2"/>
        <path d="M2.5 8h11M8 2.5a9 9 0 010 11M8 2.5a9 9 0 000 11" stroke={SB.textDim} strokeWidth="1.2"/>
      </svg>
    );
    return (
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
        <circle cx="8" cy="8" r="2" stroke={SB.textDim} strokeWidth="1.2"/>
        <circle cx="8" cy="8" r="5.5" stroke={SB.textDim} strokeWidth="1.2" strokeDasharray="2 2"/>
      </svg>
    );
  };

  return (
    <SBFrame typefaces={typefaces} activeTab="tasks">
      <div style={{ flex: 1, padding: '14px 0 0', overflow: 'hidden' }}>
        <div style={{ padding: '0 20px 14px', display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
          <div style={{ fontFamily: typefaces.display, fontSize: 36, fontWeight: 400, color: SB.text, letterSpacing: -0.8, fontStyle: 'italic' }}>Tasks</div>
          <CapsLabel typefaces={typefaces}>9 to do</CapsLabel>
        </div>

        {sections.map((s, si) => (
          <div key={si}>
            <div style={{
              padding: '9px 20px 7px', display: 'flex', alignItems: 'center', gap: 8,
              borderTop: `0.5px solid ${SB.hairline}`,
              background: s.kind === 'store' && s.dist === '0.8 mi' ? SB.buckets.Projects.bg + '00' : 'transparent',
            }}>
              {kindIcon(s.kind)}
              <span style={{ fontSize: 13, color: SB.text, fontWeight: 500, fontFamily: typefaces.body, letterSpacing: -0.1 }}>{s.name}</span>
              {s.dist && (
                <span style={{ fontSize: 10.5, color: SB.accent, fontFamily: typefaces.mono, background: SB.accentDim, padding: '2px 6px', borderRadius: 999, letterSpacing: 0.2 }}>
                  {s.dist}
                </span>
              )}
              <span style={{ flex: 1 }} />
              <span style={{ fontSize: 10.5, color: SB.textFaint, fontFamily: typefaces.mono }}>{s.items.length}</span>
              <IconChevron size={11} color={SB.textMuted} dir="down" />
            </div>
            {s.items.map((t, i) => (
              <div key={i} style={{
                padding: '10px 20px', display: 'flex', alignItems: 'center', gap: 11,
                borderTop: `0.5px solid ${SB.hairline}`,
              }}>
                <div style={{
                  width: 17, height: 17, borderRadius: 9,
                  border: `1.2px solid ${SB.textFaint}`, flexShrink: 0,
                }} />
                <div style={{ flex: 1, minWidth: 0, fontSize: 13.5, color: SB.text, lineHeight: 1.4, letterSpacing: -0.15 }}>
                  {t.t}
                </div>
                <BucketIconGeo bucket={t.bucket} size={7} color={SB.buckets[t.bucket].dot} />
                {t.buy && (
                  <div style={{ fontSize: 10, color: SB.accent, fontFamily: typefaces.mono, background: SB.accentDim, padding: '2px 6px', borderRadius: 6, letterSpacing: 0.3 }}>
                    BUY
                  </div>
                )}
              </div>
            ))}
          </div>
        ))}

        {/* GPS hint footer */}
        <div style={{
          margin: '16px 16px 0', padding: '10px 12px',
          borderRadius: 10, background: SB.surface,
          border: `0.5px dashed ${SB.hairline}`,
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <circle cx="6" cy="6" r="1.5" fill={SB.accent}/>
            <circle cx="6" cy="6" r="4" stroke={SB.accent} strokeWidth="1" strokeOpacity="0.5"/>
          </svg>
          <span style={{ fontSize: 11, color: SB.textDim, fontStyle: 'italic', fontFamily: typefaces.body, lineHeight: 1.3 }}>
            Nudge me when I'm near Target · 3 items
          </span>
        </div>
      </div>
    </SBFrame>
  );
};

// B: Today — a "what should I do right now" view, ordered
const TasksB_Today = ({ typefaces = TYPE.serif }) => {
  const items = [
    { t: 'Draft two PPTX layout strategies', bucket: 'Projects', est: '45m', priority: true },
    { t: 'Reply to Sarah re: Q3 timeline', bucket: 'People', est: '5m' },
    { t: 'Renew car registration', bucket: 'Admin', est: '10m', online: true },
    { t: 'Review Stryker deck', bucket: 'Projects', est: '20m' },
  ];
  const later = [
    { t: 'Send birthday card to Don', bucket: 'People', when: 'Mar 12' },
    { t: 'Prototype DSPy layout learner', bucket: 'Ideas', when: 'this week' },
  ];

  return (
    <SBFrame typefaces={typefaces} activeTab="tasks">
      <div style={{ flex: 1, padding: '14px 20px 0', overflow: 'hidden' }}>
        <div>
          <CapsLabel typefaces={typefaces}>Thu · Feb 21</CapsLabel>
          <div style={{ marginTop: 4, fontFamily: typefaces.display, fontSize: 36, fontWeight: 400, color: SB.text, letterSpacing: -0.8, fontStyle: 'italic' }}>
            Do today.
          </div>
          <div style={{ fontSize: 12, color: SB.textDim, marginTop: 2 }}>
            ~1h 20m across 4 things
          </div>
        </div>

        <div style={{ marginTop: 18 }}>
          {items.map((t, i) => (
            <div key={i} style={{
              padding: '12px 0', display: 'flex', alignItems: 'center', gap: 12,
              borderBottom: `0.5px solid ${SB.hairline}`,
            }}>
              <div style={{
                width: 18, height: 18, borderRadius: 9, flexShrink: 0,
                border: `1.2px solid ${t.priority ? SB.accent : SB.textFaint}`,
                background: t.priority ? SB.accentDim : 'transparent',
              }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 14, color: SB.text, lineHeight: 1.35, letterSpacing: -0.15 }}>{t.t}</div>
                <div style={{ marginTop: 4, display: 'flex', alignItems: 'center', gap: 8 }}>
                  <BucketIconGeo bucket={t.bucket} size={8} color={SB.buckets[t.bucket].dot} />
                  <span style={{ fontSize: 10.5, color: SB.buckets[t.bucket].fg, fontFamily: typefaces.mono, letterSpacing: 0.3 }}>
                    {t.bucket.toUpperCase()}
                  </span>
                </div>
              </div>
              <div style={{ fontSize: 11, color: SB.textDim, fontFamily: typefaces.mono, fontVariantNumeric: 'tabular-nums' }}>
                {t.est}
              </div>
            </div>
          ))}
        </div>

        <div style={{ marginTop: 18 }}>
          <CapsLabel typefaces={typefaces}>Later</CapsLabel>
          {later.map((t, i) => (
            <div key={i} style={{ padding: '10px 0', display: 'flex', alignItems: 'center', gap: 10 }}>
              <BucketIconLine bucket={t.bucket} size={12} color={SB.buckets[t.bucket].dot} />
              <span style={{ flex: 1, fontSize: 13, color: SB.textDim, letterSpacing: -0.15 }}>{t.t}</span>
              <span style={{ fontSize: 10.5, color: SB.textFaint, fontFamily: typefaces.mono }}>{t.when}</span>
            </div>
          ))}
        </div>
      </div>
    </SBFrame>
  );
};

// C: Agent proposals — tasks the agent has generated for you to approve
const TasksC_Proposals = ({ typefaces = TYPE.serif }) => {
  const props_ = [
    { t: 'Email Sarah summary of Stryker meeting', from: 'Meeting with Sarah · 2d ago', bucket: 'People', conf: 0.82 },
    { t: 'Schedule call with Don re: medtech engine', from: 'Note · "Talk to Don..."', bucket: 'People', conf: 0.74 },
    { t: 'Add DSPy layout idea to research doc', from: 'Idea · 3d old', bucket: 'Ideas', conf: 0.91 },
  ];

  return (
    <SBFrame typefaces={typefaces} activeTab="tasks">
      <div style={{ flex: 1, padding: '14px 20px 0', overflow: 'hidden' }}>
        <CapsLabel typefaces={typefaces} color={SB.accent}>Agent proposals</CapsLabel>
        <div style={{ marginTop: 4, fontFamily: typefaces.display, fontSize: 32, fontWeight: 400, color: SB.text, letterSpacing: -0.7, fontStyle: 'italic', lineHeight: 1.1 }}>
          Based on yesterday,<br/>should I do these?
        </div>

        <div style={{ marginTop: 18, display: 'flex', flexDirection: 'column', gap: 10 }}>
          {props_.map((p, i) => {
            const b = SB.buckets[p.bucket];
            return (
              <div key={i} style={{
                background: SB.surface, borderRadius: 14, padding: '12px 14px',
                border: `0.5px solid ${SB.hairline}`,
              }}>
                <div style={{ display:'flex', alignItems:'center', gap: 6, marginBottom: 6 }}>
                  <BucketIconLine bucket={p.bucket} size={12} color={b.fg} />
                  <span style={{ fontSize: 10.5, color: b.fg, fontFamily: typefaces.mono, letterSpacing: 0.3 }}>{p.bucket.toUpperCase()}</span>
                  <span style={{ fontSize: 10.5, color: SB.textFaint }}>·</span>
                  <span style={{ fontSize: 10.5, color: SB.textMuted, fontFamily: typefaces.mono }}>{(p.conf*100).toFixed(0)}%</span>
                </div>
                <div style={{ fontSize: 14, color: SB.text, lineHeight: 1.4, letterSpacing: -0.15 }}>{p.t}</div>
                <div style={{ marginTop: 4, fontSize: 10.5, color: SB.textMuted, fontStyle: 'italic', fontFamily: typefaces.body }}>
                  from {p.from}
                </div>
                <div style={{ marginTop: 10, display: 'flex', gap: 6 }}>
                  <div style={{ flex: 1, textAlign:'center', padding:'7px 0', borderRadius: 8, background: SB.accent, color: '#0a0a12', fontSize: 12, fontWeight: 600, fontFamily: typefaces.body }}>
                    Accept
                  </div>
                  <div style={{ flex: 1, textAlign:'center', padding:'7px 0', borderRadius: 8, border: `0.5px solid ${SB.hairline}`, color: SB.textDim, fontSize: 12, fontWeight: 500, fontFamily: typefaces.body }}>
                    Skip
                  </div>
                  <div style={{ width: 36, textAlign:'center', padding:'7px 0', borderRadius: 8, border: `0.5px solid ${SB.hairline}`, color: SB.textMuted, fontSize: 14, fontFamily: typefaces.body }}>
                    ⋯
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </SBFrame>
  );
};

// Keep TasksA_Grouped name as alias for existing call sites in index
const TasksA_Grouped = TasksA_ByBucket;

Object.assign(window, { TasksA_Grouped, TasksA_ByBucket, TasksB_Today, TasksC_Proposals, DigestA_Briefing, HITL_Clarify, StatusA, SettingsA });

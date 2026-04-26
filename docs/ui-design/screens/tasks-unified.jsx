// Unified Tasks — segmented toggle over one task pool, three views.
// Self-contained stateful component; replaces separate TasksA/B/C artboards.

const TASK_POOL = [
  { t: 'Pick up printer ink',         bucket: 'Admin',    dest: 'Target',     kind: 'store', dist: '0.8 mi', est: '5m',  today: false, priority: false, proposal: null },
  { t: 'Birthday card for Don',       bucket: 'People',   dest: 'Target',     kind: 'store', dist: '0.8 mi', est: '5m',  today: true,  priority: false, proposal: null },
  { t: 'New chisel set',              bucket: 'Ideas',    dest: 'Target',     kind: 'store', dist: '0.8 mi', est: '10m', today: false, priority: false, proposal: null },
  { t: 'Oak boards (2× 6ft)',         bucket: 'Ideas',    dest: 'Home Depot', kind: 'store', dist: '2.1 mi', est: '15m', today: false, priority: false, proposal: null },
  { t: 'Return the blue jacket',      bucket: 'Admin',    dest: 'amazon.com', kind: 'online',                est: '3m',  today: false, priority: false, proposal: null },
  { t: 'Reorder coffee beans',        bucket: 'Admin',    dest: 'amazon.com', kind: 'online', buy: true,     est: '2m',  today: true,  priority: false, proposal: null },
  { t: 'Renew car registration',      bucket: 'Admin',    dest: 'ilsos.gov',  kind: 'online',                est: '10m', today: true,  priority: false, due: 'Mar 15', proposal: null },
  { t: 'Reply to Sarah re: Q3',       bucket: 'People',   dest: null,         kind: 'anywhere',              est: '5m',  today: true,  priority: true,  proposal: null },
  { t: 'Draft PPTX layout strategies',bucket: 'Projects', dest: null,         kind: 'anywhere',              est: '45m', today: true,  priority: true,  proposal: null },

  // Agent proposals (not yet accepted as tasks)
  { t: 'Email Sarah summary of Stryker meeting', bucket: 'People', kind: 'anywhere', proposal: { from: 'Meeting with Sarah · 2d ago', conf: 0.82 }, est: '10m' },
  { t: 'Schedule call with Don re: medtech',     bucket: 'People', kind: 'anywhere', proposal: { from: 'Note · "Talk to Don..."',     conf: 0.74 }, est: '5m' },
  { t: 'Add DSPy layout idea to research doc',   bucket: 'Ideas',  kind: 'anywhere', proposal: { from: 'Idea · 3d old',               conf: 0.91 }, est: '5m' },
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

// ── Shared task row
const TaskRow = ({ task, typefaces, showBucketTag = false }) => {
  const b = SB.buckets[task.bucket];
  return (
    <div style={{
      padding: '10px 20px', display: 'flex', alignItems: 'center', gap: 11,
      borderTop: `0.5px solid ${SB.hairline}`,
    }}>
      <div style={{
        width: 17, height: 17, borderRadius: 9,
        border: `1.2px solid ${task.priority ? SB.accent : SB.textFaint}`,
        background: task.priority ? SB.accentDim : 'transparent',
        flexShrink: 0,
      }} />
      <div style={{ flex: 1, minWidth: 0, fontSize: 13.5, color: SB.text, lineHeight: 1.4, letterSpacing: -0.15 }}>
        {task.t}
        {task.due && <span style={{ marginLeft: 6, fontSize: 10.5, color: SB.warn, fontFamily: typefaces.mono }}>· {task.due}</span>}
      </div>
      {showBucketTag && (
        <span style={{ fontSize: 10, color: b.fg, fontFamily: typefaces.mono, letterSpacing: 0.3 }}>
          {task.bucket.toUpperCase()}
        </span>
      )}
      <BucketIconGeo bucket={task.bucket} size={7} color={b.dot} />
      {task.buy && (
        <div style={{ fontSize: 10, color: SB.accent, fontFamily: typefaces.mono, background: SB.accentDim, padding: '2px 6px', borderRadius: 6, letterSpacing: 0.3 }}>BUY</div>
      )}
      {task.est && <span style={{ fontSize: 10.5, color: SB.textMuted, fontFamily: typefaces.mono, fontVariantNumeric: 'tabular-nums', minWidth: 22, textAlign: 'right' }}>{task.est}</span>}
    </div>
  );
};

// ── View: By destination
const TasksView_Destination = ({ typefaces }) => {
  const tasks = TASK_POOL.filter(t => !t.proposal);
  const groups = {};
  tasks.forEach(t => {
    const key = t.dest || 'Anywhere';
    if (!groups[key]) groups[key] = { name: key, kind: t.kind, dist: t.dist, items: [] };
    groups[key].items.push(t);
  });
  const order = ['Target', 'Home Depot', 'amazon.com', 'ilsos.gov', 'Anywhere'];
  return (
    <div>
      {order.filter(k => groups[k]).map((k, si) => {
        const g = groups[k];
        return (
          <div key={si}>
            <div style={{
              padding: '9px 20px 7px', display: 'flex', alignItems: 'center', gap: 8,
              borderTop: `0.5px solid ${SB.hairline}`,
            }}>
              {kindIcon(g.kind)}
              <span style={{ fontSize: 13, color: SB.text, fontWeight: 500, fontFamily: typefaces.body, letterSpacing: -0.1 }}>{g.name}</span>
              {g.dist && (
                <span style={{ fontSize: 10.5, color: SB.accent, fontFamily: typefaces.mono, background: SB.accentDim, padding: '2px 6px', borderRadius: 999, letterSpacing: 0.2 }}>{g.dist}</span>
              )}
              <span style={{ flex: 1 }} />
              <span style={{ fontSize: 10.5, color: SB.textFaint, fontFamily: typefaces.mono }}>{g.items.length}</span>
            </div>
            {g.items.map((t, i) => <TaskRow key={i} task={t} typefaces={typefaces} />)}
          </div>
        );
      })}
      <div style={{
        margin: '14px 16px 0', padding: '10px 12px', borderRadius: 10,
        background: SB.surface, border: `0.5px dashed ${SB.hairline}`,
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
          <circle cx="6" cy="6" r="1.5" fill={SB.accent}/>
          <circle cx="6" cy="6" r="4" stroke={SB.accent} strokeWidth="1" strokeOpacity="0.5"/>
        </svg>
        <span style={{ fontSize: 11, color: SB.textDim, fontStyle: 'italic', fontFamily: typefaces.body }}>
          Nudge me near Target · 3 items
        </span>
      </div>
    </div>
  );
};

// ── View: Today
const TasksView_Today = ({ typefaces }) => {
  const today = TASK_POOL.filter(t => !t.proposal && t.today);
  const later = TASK_POOL.filter(t => !t.proposal && !t.today);
  const totalMin = today.reduce((a, t) => a + parseInt(t.est), 0);
  return (
    <div style={{ padding: '0 20px' }}>
      <div style={{ paddingBottom: 10, fontSize: 12, color: SB.textDim, fontFamily: typefaces.body }}>
        ~{Math.floor(totalMin / 60)}h {totalMin % 60}m across {today.length} things
      </div>
      {today.map((t, i) => (
        <div key={i} style={{
          padding: '11px 0', display: 'flex', alignItems: 'center', gap: 11,
          borderTop: `0.5px solid ${SB.hairline}`,
        }}>
          <div style={{
            width: 18, height: 18, borderRadius: 9, flexShrink: 0,
            border: `1.2px solid ${t.priority ? SB.accent : SB.textFaint}`,
            background: t.priority ? SB.accentDim : 'transparent',
          }} />
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 14, color: SB.text, lineHeight: 1.35, letterSpacing: -0.15 }}>{t.t}</div>
            <div style={{ marginTop: 3, display: 'flex', alignItems: 'center', gap: 8 }}>
              <BucketIconGeo bucket={t.bucket} size={7} color={SB.buckets[t.bucket].dot} />
              <span style={{ fontSize: 10.5, color: SB.buckets[t.bucket].fg, fontFamily: typefaces.mono, letterSpacing: 0.3 }}>{t.bucket.toUpperCase()}</span>
              {t.dest && <><span style={{fontSize:10.5,color:SB.textFaint}}>·</span><span style={{fontSize:10.5,color:SB.textMuted,fontFamily:typefaces.mono}}>{t.dest}</span></>}
            </div>
          </div>
          <span style={{ fontSize: 11, color: SB.textDim, fontFamily: typefaces.mono, fontVariantNumeric: 'tabular-nums' }}>{t.est}</span>
        </div>
      ))}
      <div style={{ marginTop: 16, paddingTop: 10, borderTop: `0.5px solid ${SB.hairline}` }}>
        <CapsLabel typefaces={typefaces}>Later</CapsLabel>
        {later.slice(0, 3).map((t, i) => (
          <div key={i} style={{ padding: '8px 0', display: 'flex', alignItems: 'center', gap: 10 }}>
            <BucketIconLine bucket={t.bucket} size={12} color={SB.buckets[t.bucket].dot} />
            <span style={{ flex: 1, fontSize: 13, color: SB.textDim, letterSpacing: -0.15 }}>{t.t}</span>
            <span style={{ fontSize: 10.5, color: SB.textFaint, fontFamily: typefaces.mono }}>{t.dest || '—'}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

// ── View: Proposals
const TasksView_Proposals = ({ typefaces }) => {
  const props_ = TASK_POOL.filter(t => t.proposal);
  return (
    <div style={{ padding: '0 16px' }}>
      <div style={{ padding: '0 4px 10px', fontSize: 12, color: SB.textDim, fontStyle: 'italic', fontFamily: typefaces.body }}>
        The agent suggests these from yesterday's captures.
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
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
                <span style={{ fontSize: 10.5, color: SB.textMuted, fontFamily: typefaces.mono }}>{(p.proposal.conf*100).toFixed(0)}%</span>
              </div>
              <div style={{ fontSize: 14, color: SB.text, lineHeight: 1.4, letterSpacing: -0.15 }}>{p.t}</div>
              <div style={{ marginTop: 4, fontSize: 10.5, color: SB.textMuted, fontStyle: 'italic', fontFamily: typefaces.body }}>from {p.proposal.from}</div>
              <div style={{ marginTop: 10, display: 'flex', gap: 6 }}>
                <div style={{ flex: 1, textAlign:'center', padding:'7px 0', borderRadius: 8, background: SB.accent, color: '#0a0a12', fontSize: 12, fontWeight: 600, fontFamily: typefaces.body }}>Accept</div>
                <div style={{ flex: 1, textAlign:'center', padding:'7px 0', borderRadius: 8, border: `0.5px solid ${SB.hairline}`, color: SB.textDim, fontSize: 12, fontWeight: 500, fontFamily: typefaces.body }}>Skip</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ── Unified screen with segmented toggle
const TasksUnified = ({ typefaces = TYPE.serif, defaultView = 'destination' }) => {
  const [view, setView] = React.useState(defaultView);

  const views = [
    { key: 'destination', label: 'Where',     count: TASK_POOL.filter(t=>!t.proposal).length },
    { key: 'today',       label: 'Today',     count: TASK_POOL.filter(t=>!t.proposal && t.today).length },
    { key: 'proposals',   label: 'Proposals', count: TASK_POOL.filter(t=>t.proposal).length },
  ];

  return (
    <SBFrame typefaces={typefaces} activeTab="tasks">
      <div style={{ flex: 1, padding: '14px 0 0', overflow: 'hidden' }}>
        {/* Header */}
        <div style={{ padding: '0 20px 12px', display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
          <div style={{ fontFamily: typefaces.display, fontSize: 36, fontWeight: 400, color: SB.text, letterSpacing: -0.8, fontStyle: 'italic' }}>Tasks</div>
          <CapsLabel typefaces={typefaces}>{TASK_POOL.filter(t=>!t.proposal).length} to do</CapsLabel>
        </div>

        {/* Segmented toggle */}
        <div style={{ margin: '0 20px 14px', padding: 3, borderRadius: 10, background: SB.surface, display: 'flex', gap: 2 }}>
          {views.map(v => {
            const active = v.key === view;
            return (
              <div key={v.key} onClick={() => setView(v.key)} style={{
                flex: 1, padding: '7px 0', textAlign: 'center', borderRadius: 8,
                background: active ? SB.surfaceHi : 'transparent',
                color: active ? SB.text : SB.textMuted,
                fontSize: 12.5, fontWeight: active ? 600 : 500, letterSpacing: -0.1,
                fontFamily: typefaces.body, cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5,
              }}>
                {v.label}
                <span style={{ fontSize: 10, color: active ? SB.textMuted : SB.textFaint, fontFamily: typefaces.mono }}>{v.count}</span>
              </div>
            );
          })}
        </div>

        {/* Content */}
        {view === 'destination' && <TasksView_Destination typefaces={typefaces} />}
        {view === 'today' && <TasksView_Today typefaces={typefaces} />}
        {view === 'proposals' && <TasksView_Proposals typefaces={typefaces} />}
      </div>
    </SBFrame>
  );
};

Object.assign(window, { TasksUnified });

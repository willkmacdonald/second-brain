// Tiny icon system — three explorations per bucket.
// All rendered as SVG so they scale crisply in the frames.

// ─── Approach A: Thin line (SF Symbols-ish) ───
function IconMic({ size = 24, color = 'currentColor', stroke = 1.5 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <rect x="9" y="3" width="6" height="12" rx="3" stroke={color} strokeWidth={stroke}/>
      <path d="M5 11a7 7 0 0014 0M12 18v3M8.5 21h7" stroke={color} strokeWidth={stroke} strokeLinecap="round"/>
    </svg>
  );
}
function IconPencil({ size = 22, color = 'currentColor', stroke = 1.5 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M4 20h4l10-10-4-4L4 16v4zM14 6l4 4" stroke={color} strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}
function IconInbox({ size = 22, color = 'currentColor', stroke = 1.5 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M4 4h16v11l-5 1-1 2h-4l-1-2-5-1V4zM4 15h4M16 15h4" stroke={color} strokeWidth={stroke} strokeLinejoin="round" strokeLinecap="round"/>
    </svg>
  );
}
function IconCheck({ size = 22, color = 'currentColor', stroke = 1.5 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <rect x="3.5" y="3.5" width="17" height="17" rx="4" stroke={color} strokeWidth={stroke}/>
      <path d="M8 12.5l3 3 5.5-6" stroke={color} strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}
function IconSpark({ size = 22, color = 'currentColor', stroke = 1.5 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <path d="M12 3v6M12 15v6M3 12h6M15 12h6M6 6l3 3M15 15l3 3M6 18l3-3M15 9l3-3" stroke={color} strokeWidth={stroke} strokeLinecap="round"/>
    </svg>
  );
}

// Bucket marks — three visual languages ─────────────────────────────

// A: Line icons
function BucketIconLine({ bucket, size = 14, color = 'currentColor' }) {
  const s = size, sw = 1.4;
  switch (bucket) {
    case 'People':
      return (<svg width={s} height={s} viewBox="0 0 16 16" fill="none">
        <circle cx="8" cy="5.5" r="2.5" stroke={color} strokeWidth={sw}/>
        <path d="M3 14c0-2.5 2.3-4.5 5-4.5s5 2 5 4.5" stroke={color} strokeWidth={sw} strokeLinecap="round"/>
      </svg>);
    case 'Projects':
      return (<svg width={s} height={s} viewBox="0 0 16 16" fill="none">
        <path d="M2 5l3-2h5l3 2v7a1 1 0 01-1 1H3a1 1 0 01-1-1V5z" stroke={color} strokeWidth={sw} strokeLinejoin="round"/>
        <path d="M2 8h12" stroke={color} strokeWidth={sw}/>
      </svg>);
    case 'Ideas':
      return (<svg width={s} height={s} viewBox="0 0 16 16" fill="none">
        <path d="M8 2a4.5 4.5 0 00-3 7.8V11.5h6V9.8A4.5 4.5 0 008 2zM6 13h4M7 14.5h2" stroke={color} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round"/>
      </svg>);
    case 'Admin':
      return (<svg width={s} height={s} viewBox="0 0 16 16" fill="none">
        <rect x="3" y="3" width="10" height="10" rx="1.5" stroke={color} strokeWidth={sw}/>
        <path d="M5.5 7l2 2 3.5-3.5" stroke={color} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round"/>
      </svg>);
  }
}

// B: Geometric glyph (filled shape, no outline)
function BucketIconGeo({ bucket, size = 14, color = 'currentColor' }) {
  const s = size;
  switch (bucket) {
    case 'People':
      return (<svg width={s} height={s} viewBox="0 0 16 16"><circle cx="8" cy="8" r="5.5" fill={color}/></svg>);
    case 'Projects':
      return (<svg width={s} height={s} viewBox="0 0 16 16"><rect x="2.5" y="2.5" width="11" height="11" rx="1.5" fill={color}/></svg>);
    case 'Ideas':
      return (<svg width={s} height={s} viewBox="0 0 16 16"><path d="M8 1.5L14.5 8 8 14.5 1.5 8z" fill={color}/></svg>);
    case 'Admin':
      return (<svg width={s} height={s} viewBox="0 0 16 16"><path d="M8 2l6 4v4l-6 4-6-4V6z" fill={color}/></svg>);
  }
}

// C: Custom mark — single-letter monogrammed initial
function BucketIconMark({ bucket, size = 16, color = 'currentColor', bg = 'transparent' }) {
  const letter = { People: 'P', Projects: 'R', Ideas: 'I', Admin: 'A' }[bucket];
  return (
    <div style={{
      width: size, height: size, borderRadius: size/3.2,
      background: bg, color, display: 'inline-flex',
      alignItems: 'center', justifyContent: 'center',
      fontFamily: 'ui-monospace, "SF Mono", Menlo, monospace',
      fontSize: size * 0.58, fontWeight: 600, letterSpacing: '-0.02em',
    }}>{letter}</div>
  );
}

// Small utility glyphs
function IconWave({ w = 120, h = 28, color = 'currentColor', active = false }) {
  const bars = 24;
  return (
    <svg width={w} height={h} viewBox={`0 0 ${bars * 4} ${h}`} fill="none">
      {Array.from({ length: bars }).map((_, i) => {
        const phase = active ? Math.sin(i * 0.6) * 0.5 + 0.5 : 0.35 + (i % 5) * 0.08;
        const hh = Math.max(2, phase * h * 0.9);
        return <rect key={i} x={i * 4 + 1} y={(h - hh) / 2} width="2" height={hh} rx="1" fill={color}/>;
      })}
    </svg>
  );
}
function IconChevron({ size = 14, color = 'currentColor', dir = 'right' }) {
  const d = { right: 'M4 2l6 5-6 5', left: 'M10 2L4 7l6 5', down: 'M2 4l5 6 5-6', up: 'M2 10l5-6 5 6' }[dir];
  return (<svg width={size} height={size} viewBox="0 0 14 14" fill="none">
    <path d={d} stroke={color} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>);
}

Object.assign(window, {
  IconMic, IconPencil, IconInbox, IconCheck, IconSpark, IconWave, IconChevron,
  BucketIconLine, BucketIconGeo, BucketIconMark,
});

// Shared screen shell — device frame minus extras, tuned for Second Brain.
// Gives each screen a consistent status bar, safe areas, and optional tab bar.

const SBFrame = ({ children, typefaces = TYPE.system, showTabBar = true, activeTab = 'capture', bg = SB.bg, width = 320, height = 660, noPad = false }) => {
  return (
    <div style={{
      width, height, borderRadius: 42, overflow: 'hidden',
      position: 'relative', background: bg,
      boxShadow: '0 30px 60px rgba(0,0,0,0.32), 0 0 0 1px rgba(255,255,255,0.04)',
      fontFamily: typefaces.body,
      color: SB.text,
      WebkitFontSmoothing: 'antialiased',
    }}>
      {/* Dynamic island */}
      <div style={{
        position: 'absolute', top: 9, left: '50%', transform: 'translateX(-50%)',
        width: 100, height: 30, borderRadius: 20, background: '#000', zIndex: 50,
      }} />
      {/* Status bar */}
      <div style={{
        position: 'absolute', top: 0, left: 0, right: 0, zIndex: 40,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '14px 26px 0', color: SB.text,
      }}>
        <span style={{ fontSize: 14, fontWeight: 600, letterSpacing: -0.2, fontFamily: typefaces.body }}>9:41</span>
        <div style={{ display: 'flex', gap: 5, alignItems: 'center', paddingTop: 1 }}>
          <svg width="15" height="10" viewBox="0 0 15 10"><rect x="0" y="6" width="2.5" height="4" rx="0.5" fill={SB.text}/><rect x="3.8" y="4" width="2.5" height="6" rx="0.5" fill={SB.text}/><rect x="7.6" y="2" width="2.5" height="8" rx="0.5" fill={SB.text}/><rect x="11.4" y="0" width="2.5" height="10" rx="0.5" fill={SB.text}/></svg>
          <svg width="22" height="10" viewBox="0 0 22 10"><rect x="0.4" y="0.4" width="18.6" height="9.2" rx="2.5" stroke={SB.text} strokeOpacity="0.35" fill="none"/><rect x="1.6" y="1.6" width="16.2" height="6.8" rx="1.4" fill={SB.text}/></svg>
        </div>
      </div>

      {/* Content */}
      <div style={{
        position: 'absolute', inset: 0,
        paddingTop: noPad ? 0 : 42,
        paddingBottom: showTabBar ? 70 : 28,
        display: 'flex', flexDirection: 'column', overflow: 'hidden',
      }}>
        {children}
      </div>

      {/* Tab bar */}
      {showTabBar && <SBTabBar active={activeTab} typefaces={typefaces} />}

      {/* Home indicator */}
      <div style={{
        position: 'absolute', bottom: 7, left: '50%', transform: 'translateX(-50%)',
        width: 110, height: 4, borderRadius: 100, background: 'rgba(255,255,255,0.55)', zIndex: 60,
      }} />
    </div>
  );
};

// ─── Tab bar ───
const SBTabBar = ({ active = 'capture', typefaces = TYPE.system }) => {
  const tabs = [
    { key: 'capture', label: 'Capture', Icon: (p) => <IconMic {...p} /> },
    { key: 'inbox',   label: 'Inbox',   Icon: (p) => <IconInbox {...p} />, badge: 2 },
    { key: 'tasks',   label: 'Tasks',   Icon: (p) => <IconCheck {...p} /> },
    { key: 'status',  label: 'Status',  Icon: (p) => <IconSpark {...p} /> },
  ];
  return (
    <div style={{
      position: 'absolute', left: 0, right: 0, bottom: 0, height: 70,
      borderTop: `0.5px solid ${SB.hairline}`,
      background: 'rgba(10,10,18,0.85)',
      backdropFilter: 'blur(20px)',
      display: 'flex', zIndex: 55,
    }}>
      {tabs.map(t => {
        const isActive = t.key === active;
        const c = isActive ? SB.text : SB.textMuted;
        return (
          <div key={t.key} style={{
            flex: 1, display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', gap: 3, paddingTop: 6,
            color: c, position: 'relative',
          }}>
            <div style={{ position: 'relative' }}>
              <t.Icon size={22} color={c} stroke={isActive ? 1.8 : 1.4} />
              {t.badge && (
                <div style={{
                  position: 'absolute', top: -3, right: -7,
                  width: 14, height: 14, borderRadius: 7,
                  background: SB.accent, color: '#fff',
                  fontSize: 9, fontWeight: 700,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontFamily: typefaces.body,
                }}>{t.badge}</div>
              )}
            </div>
            <span style={{
              fontSize: 10.5, fontWeight: isActive ? 600 : 500,
              letterSpacing: -0.1, fontFamily: typefaces.body,
            }}>{t.label}</span>
          </div>
        );
      })}
    </div>
  );
};

// ─── Bucket chip (variant A: pill, muted fill) ───
const BucketChip = ({ bucket, variant = 'pill', iconStyle = 'line', size = 'sm', typefaces = TYPE.system }) => {
  const b = SB.buckets[bucket];
  const Icon = iconStyle === 'line' ? BucketIconLine : iconStyle === 'geo' ? BucketIconGeo : BucketIconMark;
  const fontSize = size === 'sm' ? 11 : 13;
  const padV = size === 'sm' ? 3 : 5;
  const padH = size === 'sm' ? 8 : 10;
  const isTag = variant === 'tag';
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: `${padV}px ${padH}px`,
      borderRadius: 999,
      background: isTag ? 'transparent' : b.bg,
      border: isTag ? `0.5px solid ${b.dot}55` : `0.5px solid ${b.fg}20`,
      color: b.fg,
      fontSize, fontWeight: 500, letterSpacing: -0.1,
      fontFamily: typefaces.label,
    }}>
      <Icon bucket={bucket} size={fontSize + 1} color={b.fg} />
      {bucket}
    </span>
  );
};

// ─── Caption / label in all-caps mono ───
const CapsLabel = ({ children, color = SB.textMuted, typefaces = TYPE.system, size = 10 }) => (
  <span style={{
    fontFamily: typefaces.label, fontSize: size, fontWeight: 600,
    letterSpacing: size < 11 ? 1.4 : 1.2, textTransform: 'uppercase',
    color,
  }}>{children}</span>
);

Object.assign(window, { SBFrame, SBTabBar, BucketChip, CapsLabel });

import React from "react";
import {
  AbsoluteFill,
  Audio,
  interpolate,
  Sequence,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { EVALS_COLORS, EVALS_SCENES, EVALS_TOTAL_DURATION } from "./constants";

const font = "Arial, sans-serif";
const mono = "SF Mono, Menlo, Consolas, monospace";

const Background: React.FC = () => {
  const frame = useCurrentFrame();
  const offset = interpolate(frame, [0, EVALS_TOTAL_DURATION], [0, 64]);
  const glowX = interpolate(frame, [0, EVALS_TOTAL_DURATION], [18, 82]);

  return (
    <AbsoluteFill
      style={{
        background: `
          radial-gradient(circle at ${glowX}% 30%, rgba(88, 166, 255, 0.14), transparent 34%),
          radial-gradient(circle at 42% 78%, rgba(63, 185, 80, 0.10), transparent 34%),
          linear-gradient(180deg, #05070d 0%, #07111f 54%, #05070d 100%)
        `,
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage: `
            linear-gradient(rgba(148, 163, 184, 0.08) 1px, transparent 1px),
            linear-gradient(90deg, rgba(148, 163, 184, 0.08) 1px, transparent 1px)
          `,
          backgroundSize: "60px 60px",
          backgroundPosition: `${offset}px ${offset}px`,
        }}
      />
    </AbsoluteFill>
  );
};

const SectionLabel: React.FC<{ children: React.ReactNode; color?: string }> = ({
  children,
  color = EVALS_COLORS.cyan,
}) => (
  <div
    style={{
      fontFamily: font,
      fontSize: 16,
      fontWeight: 900,
      color,
      textTransform: "uppercase",
      letterSpacing: 0,
    }}
  >
    {children}
  </div>
);

const PhoneShell: React.FC<{ children: React.ReactNode; scale?: number }> = ({
  children,
  scale = 1,
}) => (
  <div
    style={{
      width: 392,
      height: 844,
      borderRadius: 48,
      padding: 10,
      background: "linear-gradient(145deg, rgba(255,255,255,0.26), rgba(255,255,255,0.06))",
      boxShadow: "0 34px 100px rgba(0,0,0,0.55), 0 0 56px rgba(88, 166, 255, 0.16)",
      transform: `scale(${scale})`,
      transformOrigin: "center",
    }}
  >
    <div
      style={{
        width: "100%",
        height: "100%",
        borderRadius: 40,
        overflow: "hidden",
        background: "#0b0d1c",
        border: "1px solid rgba(255,255,255,0.10)",
        fontFamily: font,
        color: EVALS_COLORS.text,
        position: "relative",
      }}
    >
      <div
        style={{
          height: 94,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 22px",
          borderBottom: "1px solid rgba(255,255,255,0.08)",
          background: "rgba(17, 19, 39, 0.94)",
        }}
      >
        <div
          style={{
            width: 82,
            height: 44,
            borderRadius: 22,
            border: "1px solid rgba(255,255,255,0.10)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: EVALS_COLORS.text,
            fontSize: 22,
            fontWeight: 800,
          }}
        >
          ‹
        </div>
        <div style={{ fontSize: 23, fontWeight: 900 }}>Investigate</div>
        <div
          style={{
            width: 70,
            height: 44,
            borderRadius: 22,
            background: "rgba(88, 166, 255, 0.10)",
            border: "1px solid rgba(88, 166, 255, 0.22)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: EVALS_COLORS.blue,
            fontSize: 16,
            fontWeight: 800,
          }}
        >
          New
        </div>
      </div>
      {children}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 0,
          height: 72,
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "10px 16px",
          background: "rgba(23, 26, 44, 0.96)",
          borderTop: "1px solid rgba(255,255,255,0.08)",
        }}
      >
        <div
          style={{
            flex: 1,
            height: 48,
            borderRadius: 24,
            background: "#080a18",
            color: EVALS_COLORS.dim,
            display: "flex",
            alignItems: "center",
            paddingLeft: 18,
            fontSize: 15,
          }}
        >
          Ask about your system...
        </div>
        <div
          style={{
            width: 44,
            height: 44,
            borderRadius: 22,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "rgba(88, 166, 255, 0.92)",
            color: "white",
            fontSize: 22,
            fontWeight: 900,
          }}
        >
          ↑
        </div>
      </div>
    </div>
  </div>
);

const UserBubble: React.FC<{ children: React.ReactNode; style?: React.CSSProperties }> = ({
  children,
  style,
}) => (
  <div
    style={{
      alignSelf: "flex-end",
      maxWidth: 314,
      padding: "14px 18px",
      borderRadius: 24,
      background: EVALS_COLORS.blue,
      color: "white",
      fontSize: 18,
      lineHeight: 1.22,
      ...style,
    }}
  >
    {children}
  </div>
);

const AssistantBubble: React.FC<{ children: React.ReactNode; style?: React.CSSProperties }> = ({
  children,
  style,
}) => (
  <div
    style={{
      alignSelf: "flex-start",
      width: "100%",
      padding: 18,
      borderRadius: 22,
      background: "#191b30",
      color: EVALS_COLORS.text,
      fontSize: 16,
      lineHeight: 1.45,
      ...style,
    }}
  >
    {children}
  </div>
);

const EvalStartScreen: React.FC<{ frame: number; compact?: boolean }> = ({ frame, compact }) => {
  const items = [
    { start: 42, node: <UserBubble>Run classifier eval</UserBubble> },
    {
      start: 95,
      node: (
        <AssistantBubble>
          I can trigger a classifier evaluation run using the golden dataset. Would you like me
          to start this evaluation?
        </AssistantBubble>
      ),
    },
    { start: 166, node: <UserBubble style={{ maxWidth: 74 }}>Yes</UserBubble> },
    {
      start: 222,
      node: (
        <AssistantBubble>
          The classifier evaluation run has started.
          <br />
          <br />
          <span style={{ color: EVALS_COLORS.muted }}>Run ID:</span>{" "}
          <span style={{ fontFamily: mono }}>3e649f65-0298</span>
          <br />
          Results will be available in a few minutes.
        </AssistantBubble>
      ),
    },
  ];

  return (
    <PhoneShell scale={compact ? 0.82 : 1}>
      <div
        style={{
          position: "absolute",
          inset: "112px 18px 86px 18px",
          display: "flex",
          flexDirection: "column",
          justifyContent: "flex-end",
          gap: 14,
        }}
      >
        {items.map((item, index) => {
          const opacity = interpolate(frame - item.start, [0, 18], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          const y = interpolate(frame - item.start, [0, 18], [20, 0], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          return (
            <div
              key={index}
              style={{
                opacity,
                transform: `translateY(${y}px)`,
                display: "flex",
                flexDirection: "column",
              }}
            >
              {item.node}
            </div>
          );
        })}
      </div>
    </PhoneShell>
  );
};

const EvalResultsScreen: React.FC<{ frame: number; compact?: boolean }> = ({ frame, compact }) => {
  const opacity = interpolate(frame, [20, 50], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <PhoneShell scale={compact ? 0.82 : 1}>
      <div
        style={{
          position: "absolute",
          inset: "112px 18px 86px 18px",
          display: "flex",
          flexDirection: "column",
          justifyContent: "flex-end",
          gap: 14,
          opacity,
        }}
      >
        <UserBubble style={{ maxWidth: 330 }}>Yes, check the results now</UserBubble>
        <AssistantBubble style={{ fontSize: 14.6, lineHeight: 1.35 }}>
          The classifier evaluation run has completed.
          <br />
          <br />
          <b>Run ID:</b> <span style={{ fontFamily: mono }}>8696126a-2800</span>
          <br />
          <b>Dataset Size:</b> 142 samples
          <br />
          <b>Score:</b> 87%
          <br />
          <b>Precision by Bucket:</b>
          <br />
          Admin 0.91 · Projects 0.84 · People 0.88 · Ideas 0.86
          <br />
          <br />
          Confidence calibration improved week over week.
        </AssistantBubble>
      </div>
    </PhoneShell>
  );
};

const StageTitle: React.FC<{
  label: string;
  title: string;
  body: string;
  frame: number;
  delay?: number;
}> = ({ label, title, body, frame, delay = 0 }) => {
  const opacity = interpolate(frame - delay, [0, 26], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const y = interpolate(frame - delay, [0, 26], [24, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div style={{ opacity, transform: `translateY(${y}px)` }}>
      <SectionLabel>{label}</SectionLabel>
      <div
        style={{
          fontFamily: font,
          color: EVALS_COLORS.text,
          fontSize: 68,
          lineHeight: 0.96,
          fontWeight: 900,
          marginTop: 14,
          maxWidth: 760,
        }}
      >
        {title}
      </div>
      <div
        style={{
          fontFamily: font,
          color: EVALS_COLORS.muted,
          fontSize: 28,
          lineHeight: 1.28,
          marginTop: 24,
          maxWidth: 720,
        }}
      >
        {body}
      </div>
    </div>
  );
};

const StepCard: React.FC<{
  frame: number;
  delay: number;
  step: string;
  title: string;
  detail: string;
}> = ({ frame, delay, step, title, detail }) => {
  const enter = spring({ frame: frame - delay, fps: 30, config: { damping: 15, stiffness: 80 } });
  const opacity = interpolate(frame - delay, [0, 18], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        opacity,
        transform: `translateX(${interpolate(enter, [0, 1], [28, 0])}px)`,
        display: "grid",
        gridTemplateColumns: "54px 1fr",
        gap: 16,
        alignItems: "center",
        padding: 18,
        borderRadius: 20,
        background: EVALS_COLORS.panelGlass,
        border: `1px solid ${EVALS_COLORS.border}`,
      }}
    >
      <div
        style={{
          width: 54,
          height: 54,
          borderRadius: 18,
          background: "rgba(88, 166, 255, 0.14)",
          border: "1px solid rgba(88, 166, 255, 0.36)",
          color: EVALS_COLORS.blue,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: mono,
          fontSize: 19,
          fontWeight: 900,
        }}
      >
        {step}
      </div>
      <div>
        <div style={{ fontFamily: font, color: EVALS_COLORS.text, fontSize: 22, fontWeight: 900 }}>
          {title}
        </div>
        <div style={{ fontFamily: font, color: EVALS_COLORS.muted, fontSize: 16, marginTop: 5 }}>
          {detail}
        </div>
      </div>
    </div>
  );
};

const TriggerEvalScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const phoneEnter = spring({ frame, fps, config: { damping: 17, stiffness: 78 } });

  return (
    <AbsoluteFill style={{ padding: 74 }}>
      <div style={{ display: "flex", alignItems: "center", height: "100%", gap: 78 }}>
        <div
          style={{
            width: 500,
            display: "flex",
            justifyContent: "center",
            transform: `translateX(${interpolate(phoneEnter, [0, 1], [-70, 0])}px) rotate(-3deg)`,
          }}
        >
          <EvalStartScreen frame={frame} />
        </div>
        <div style={{ flex: 1 }}>
          <StageTitle
            label="Evaluation"
            title="Run an eval from the phone."
            body="The investigation agent triggers the classifier evaluation and returns the status in the same mobile workflow."
            frame={frame}
          />
          <div style={{ display: "grid", gap: 14, marginTop: 42, maxWidth: 720 }}>
            <StepCard
              frame={frame}
              delay={68}
              step="01"
              title="Ask the investigation agent"
              detail="Natural-language request: run classifier eval."
            />
            <StepCard
              frame={frame}
              delay={142}
              step="02"
              title="Confirm the run"
              detail="The agent explains the background process and asks for approval."
            />
            <StepCard
              frame={frame}
              delay={226}
              step="03"
              title="Eval started"
              detail="A run ID comes back immediately; results can be checked later."
            />
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

const StatCard: React.FC<{
  label: string;
  value: string;
  color?: string;
  frame: number;
  delay: number;
}> = ({ label, value, color = EVALS_COLORS.text, frame, delay }) => {
  const opacity = interpolate(frame - delay, [0, 18], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        opacity,
        padding: 20,
        borderRadius: 20,
        background: "rgba(8, 13, 25, 0.74)",
        border: `1px solid ${EVALS_COLORS.border}`,
        minHeight: 126,
      }}
    >
      <div
        style={{
          fontFamily: font,
          color: EVALS_COLORS.dim,
          fontSize: 13,
          fontWeight: 900,
          textTransform: "uppercase",
          letterSpacing: 0,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontFamily: font,
          color,
          fontSize: 38,
          fontWeight: 900,
          marginTop: 13,
        }}
      >
        {value}
      </div>
    </div>
  );
};

const EvalResultsPanel: React.FC<{ frame: number }> = ({ frame }) => {
  const rows = [
    ["Correct", "124", EVALS_COLORS.green],
    ["Incorrect", "11", EVALS_COLORS.red],
    ["Low Confidence", "7", EVALS_COLORS.amber],
  ];
  const patterns = [
    "Projects vs Ideas confusion on hobby captures",
    "Admin vs Projects when a deadline is mentioned",
    "Low confidence when location is implied, not stated",
  ];
  const enter = spring({ frame, fps: 30, config: { damping: 17, stiffness: 74 } });

  return (
    <div
      style={{
        width: 1010,
        padding: 32,
        borderRadius: 30,
        background: "rgba(17, 24, 39, 0.76)",
        border: "1px solid rgba(255,255,255,0.14)",
        boxShadow: "0 40px 120px rgba(0,0,0,0.42), 0 0 70px rgba(88,166,255,0.10)",
        transform: `translateY(${interpolate(enter, [0, 1], [34, 0])}px)`,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start" }}>
        <div>
          <SectionLabel color={EVALS_COLORS.green}>Classifier Evaluation</SectionLabel>
          <div
            style={{
              fontFamily: font,
              color: EVALS_COLORS.text,
              fontSize: 44,
              fontWeight: 900,
              marginTop: 8,
            }}
          >
            Eval results are readable.
          </div>
        </div>
        <div
          style={{
            fontFamily: mono,
            color: EVALS_COLORS.muted,
            fontSize: 17,
            padding: "14px 18px",
            borderRadius: 14,
            background: "rgba(0,0,0,0.22)",
            border: `1px solid ${EVALS_COLORS.border}`,
          }}
        >
          run_8696126a
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginTop: 28 }}>
        <StatCard label="Date" value="Apr 25" frame={frame} delay={20} />
        <StatCard label="Score" value="87%" color={EVALS_COLORS.green} frame={frame} delay={46} />
        <StatCard label="Samples" value="142" frame={frame} delay={72} />
        <StatCard label="Model" value="GPT-4o" color={EVALS_COLORS.blue} frame={frame} delay={98} />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "0.92fr 1.08fr", gap: 20, marginTop: 22 }}>
        <div
          style={{
            padding: 22,
            borderRadius: 22,
            background: "rgba(8, 13, 25, 0.74)",
            border: `1px solid ${EVALS_COLORS.border}`,
          }}
        >
          <div style={{ fontFamily: font, color: EVALS_COLORS.text, fontSize: 24, fontWeight: 900 }}>
            Breakdown
          </div>
          <div style={{ display: "grid", gap: 12, marginTop: 18 }}>
            {rows.map(([label, value, color], index) => {
              const opacity = interpolate(frame - 126 - index * 18, [0, 14], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              });
              return (
                <div
                  key={label}
                  style={{
                    opacity,
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "14px 16px",
                    borderRadius: 14,
                    background: "rgba(255,255,255,0.04)",
                    fontFamily: font,
                  }}
                >
                  <div style={{ color: EVALS_COLORS.muted, fontSize: 18 }}>{label}</div>
                  <div style={{ color, fontSize: 23, fontWeight: 900 }}>{value}</div>
                </div>
              );
            })}
          </div>
        </div>
        <div
          style={{
            padding: 22,
            borderRadius: 22,
            background: "rgba(8, 13, 25, 0.74)",
            border: `1px solid ${EVALS_COLORS.border}`,
          }}
        >
          <div style={{ fontFamily: font, color: EVALS_COLORS.text, fontSize: 24, fontWeight: 900 }}>
            Failure Patterns
          </div>
          <div style={{ display: "grid", gap: 13, marginTop: 18 }}>
            {patterns.map((pattern, index) => {
              const opacity = interpolate(frame - 144 - index * 24, [0, 16], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              });
              return (
                <div
                  key={pattern}
                  style={{
                    opacity,
                    display: "grid",
                    gridTemplateColumns: "12px 1fr",
                    gap: 12,
                    alignItems: "start",
                    fontFamily: font,
                    color: EVALS_COLORS.muted,
                    fontSize: 18,
                    lineHeight: 1.25,
                  }}
                >
                  <div
                    style={{
                      width: 9,
                      height: 9,
                      borderRadius: 5,
                      background: EVALS_COLORS.amber,
                      marginTop: 7,
                      boxShadow: "0 0 14px rgba(210,153,34,0.6)",
                    }}
                  />
                  <div>{pattern}</div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};

const ResultsScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const phone = spring({ frame, fps, config: { damping: 18, stiffness: 70 } });

  return (
    <AbsoluteFill style={{ padding: "72px 78px" }}>
      <div style={{ display: "flex", alignItems: "center", height: "100%", gap: 36 }}>
        <div
          style={{
            width: 360,
            display: "flex",
            justifyContent: "center",
            transform: `translateX(${interpolate(phone, [0, 1], [120, 0])}px) rotate(-4deg)`,
            opacity: interpolate(frame, [0, 35], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          <EvalResultsScreen frame={frame} compact />
        </div>
        <EvalResultsPanel frame={frame} />
      </div>
    </AbsoluteFill>
  );
};

const TrendChart: React.FC<{
  frame: number;
  title: string;
  values?: number[];
  color?: string;
}> = ({ frame, title, values = [78, 82, 85, 84, 87, 89], color = EVALS_COLORS.green }) => {
  const progress = interpolate(frame, [40, 210], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const width = 780;
  const height = 310;
  const points = values
    .map((value, index) => {
      const x = 70 + (index * (width - 120)) / (values.length - 1);
      const y = 250 - ((value - 72) / 22) * 190;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <div
      style={{
        padding: 30,
        borderRadius: 28,
        background: EVALS_COLORS.panelGlass,
        border: `1px solid ${EVALS_COLORS.border}`,
        boxShadow: "0 36px 110px rgba(0,0,0,0.36)",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ fontFamily: font, color: EVALS_COLORS.text, fontSize: 34, fontWeight: 900 }}>
          {title}
        </div>
        <div style={{ fontFamily: font, color, fontSize: 38, fontWeight: 900 }}>
          {values[values.length - 1]}%
        </div>
      </div>
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ marginTop: 20 }}>
        {[78, 84, 90].map((tick) => {
          const y = 250 - ((tick - 72) / 22) * 190;
          return (
            <g key={tick}>
              <line x1="58" x2={width - 38} y1={y} y2={y} stroke="rgba(255,255,255,0.10)" />
              <text x="4" y={y + 6} fill={EVALS_COLORS.dim} fontFamily={font} fontSize="16">
                {tick}%
              </text>
            </g>
          );
        })}
        {["W1", "W2", "W3", "W4", "W5", "W6"].map((week, index) => {
          const x = 70 + (index * (width - 120)) / 5;
          return (
            <text key={week} x={x - 12} y="292" fill={EVALS_COLORS.dim} fontFamily={font} fontSize="17">
              {week}
            </text>
          );
        })}
        <polyline
          points={points}
          fill="none"
          stroke={color}
          strokeWidth="7"
          strokeLinecap="round"
          strokeLinejoin="round"
          pathLength="1"
          strokeDasharray="1"
          strokeDashoffset={1 - progress}
          style={{ filter: `drop-shadow(0 0 18px ${color}88)` }}
        />
        {values.map((value, index) => {
          const visible = progress > index / values.length;
          const x = 70 + (index * (width - 120)) / (values.length - 1);
          const y = 250 - ((value - 72) / 22) * 190;
          return (
            <circle
              key={index}
              cx={x}
              cy={y}
              r={visible ? 8 : 0}
              fill={color}
              stroke="#07111f"
              strokeWidth="4"
            />
          );
        })}
      </svg>
    </div>
  );
};

const Flywheel: React.FC<{ frame: number; labels: string[]; compact?: boolean }> = ({
  frame,
  labels,
  compact,
}) => {
  const radius = compact ? 134 : 166;
  const center = compact ? 190 : 236;
  const size = compact ? 380 : 472;

  return (
    <div
      style={{
        width: size,
        height: size,
        position: "relative",
        borderRadius: size / 2,
        border: "1px solid rgba(88,166,255,0.20)",
        background: "radial-gradient(circle, rgba(88,166,255,0.14), rgba(17,24,39,0.70) 58%, rgba(17,24,39,0.40))",
      }}
    >
      <div
        style={{
          position: "absolute",
          left: center - 72,
          top: center - 72,
          width: 144,
          height: 144,
          borderRadius: 72,
          background: "rgba(5,7,13,0.82)",
          border: `1px solid ${EVALS_COLORS.border}`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          textAlign: "center",
          color: EVALS_COLORS.text,
          fontFamily: font,
          fontSize: 21,
          fontWeight: 900,
          lineHeight: 1.05,
        }}
      >
        eval
        <br />
        loop
      </div>
      {labels.map((label, index) => {
        const angle = -90 + index * 90;
        const radians = (angle * Math.PI) / 180;
        const x = center + Math.cos(radians) * radius;
        const y = center + Math.sin(radians) * radius;
        const active = interpolate(frame - index * 38, [80, 118], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        return (
          <div
            key={label}
            style={{
              position: "absolute",
              left: x - 78,
              top: y - 34,
              width: 156,
              height: 68,
              borderRadius: 18,
              background: active > 0.5 ? "rgba(63,185,80,0.18)" : "rgba(8,13,25,0.82)",
              border: `1px solid ${active > 0.5 ? EVALS_COLORS.green : EVALS_COLORS.border}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              textAlign: "center",
              color: active > 0.5 ? EVALS_COLORS.text : EVALS_COLORS.muted,
              fontFamily: font,
              fontSize: compact ? 16 : 18,
              fontWeight: 900,
              boxShadow: active > 0.5 ? "0 0 28px rgba(63,185,80,0.24)" : "none",
            }}
          >
            {label}
          </div>
        );
      })}
      <div
        style={{
          position: "absolute",
          left: center - 22,
          top: 28,
          color: EVALS_COLORS.cyan,
          fontSize: 34,
          transform: `rotate(${interpolate(frame, [0, 360], [0, 360])}deg)`,
        }}
      >
        ↻
      </div>
    </div>
  );
};

const TrendFlywheelScene: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill style={{ padding: "72px 88px" }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 520px", gap: 48, alignItems: "center", height: "100%" }}>
        <div>
          <StageTitle
            label="Self Improvement"
            title="Evidence improves the system."
            body="The eval report becomes a measurable flywheel: capture, act, preserve evidence, improve the agent, then measure again."
            frame={frame}
          />
          <div style={{ marginTop: 34 }}>
            <TrendChart frame={frame} title="Classifier Accuracy" />
          </div>
        </div>
        <div style={{ display: "flex", justifyContent: "center", alignItems: "center" }}>
          <Flywheel frame={frame} labels={["Capture", "Action", "Evidence", "Improve"]} />
        </div>
      </div>
    </AbsoluteFill>
  );
};

const SpdBridgeScene: React.FC = () => {
  const frame = useCurrentFrame();
  const fade = interpolate(frame, [0, 32], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ padding: "70px 82px" }}>
      <div
        style={{
          opacity: fade,
          height: "100%",
          display: "grid",
          gridTemplateColumns: "1.05fr 0.95fr",
          gap: 42,
          alignItems: "center",
        }}
      >
        <div>
          <SectionLabel color={EVALS_COLORS.amber}>Sterile Processing Intelligence Platform</SectionLabel>
          <div
            style={{
              fontFamily: font,
              color: EVALS_COLORS.text,
              fontSize: 62,
              lineHeight: 1,
              fontWeight: 900,
              marginTop: 12,
              maxWidth: 840,
            }}
          >
            Compliance agents get better over time, and you can prove it.
          </div>
          <div style={{ marginTop: 36 }}>
            <TrendChart
              frame={frame}
              title="Compliance Agent Accuracy"
              values={[81, 84, 86, 87, 90, 92]}
              color={EVALS_COLORS.cyan}
            />
          </div>
        </div>
        <div style={{ display: "grid", justifyItems: "center", gap: 30 }}>
          <Flywheel frame={frame} labels={["Sterilize", "Validate", "Trace", "Improve"]} compact />
          <div
            style={{
              display: "flex",
              gap: 12,
              flexWrap: "wrap",
              justifyContent: "center",
              fontFamily: font,
              color: EVALS_COLORS.text,
              fontSize: 26,
              fontWeight: 900,
            }}
          >
            {["Auditable.", "Explainable.", "Improvable."].map((word, index) => (
              <div
                key={word}
                style={{
                  opacity: interpolate(frame - 80 - index * 24, [0, 18], [0, 1], {
                    extrapolateLeft: "clamp",
                    extrapolateRight: "clamp",
                  }),
                  padding: "12px 18px",
                  borderRadius: 18,
                  background: "rgba(63,185,80,0.12)",
                  border: "1px solid rgba(63,185,80,0.34)",
                }}
              >
                {word}
              </div>
            ))}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

export const BreakoutEvalsVideo: React.FC = () => {
  return (
    <>
      <Background />
      <Audio src={staticFile("breakout-evals.mp3")} />
      <Sequence from={EVALS_SCENES.trigger.start} durationInFrames={EVALS_SCENES.trigger.duration}>
        <TriggerEvalScene />
      </Sequence>
      <Sequence from={EVALS_SCENES.results.start} durationInFrames={EVALS_SCENES.results.duration}>
        <ResultsScene />
      </Sequence>
      <Sequence from={EVALS_SCENES.trend.start} durationInFrames={EVALS_SCENES.trend.duration}>
        <TrendFlywheelScene />
      </Sequence>
      <Sequence from={EVALS_SCENES.spd.start} durationInFrames={EVALS_SCENES.spd.duration}>
        <SpdBridgeScene />
      </Sequence>
    </>
  );
};

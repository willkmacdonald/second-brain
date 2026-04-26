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
import { OBS_COLORS, OBS_SCENES, OBS_TOTAL_DURATION } from "./constants";

const font = "Arial, sans-serif";
const mono = "SF Mono, Menlo, Consolas, monospace";

const Background: React.FC = () => {
  const frame = useCurrentFrame();
  const gridOffset = interpolate(frame, [0, OBS_TOTAL_DURATION], [0, 56]);
  const scanlineY = interpolate(frame, [0, OBS_TOTAL_DURATION], [-12, 112]);

  return (
    <AbsoluteFill
      style={{
        background: `
          radial-gradient(ellipse at 50% 18%, rgba(88, 166, 255, 0.12) 0%, rgba(88, 166, 255, 0.03) 34%, transparent 64%),
          linear-gradient(180deg, #05070d 0%, #07111f 50%, #05070d 100%)
        `,
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage: `
            linear-gradient(rgba(100, 116, 139, 0.08) 1px, transparent 1px),
            linear-gradient(90deg, rgba(100, 116, 139, 0.08) 1px, transparent 1px)
          `,
          backgroundSize: "58px 58px",
          backgroundPosition: `${gridOffset}px ${gridOffset}px`,
        }}
      />
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: `${scanlineY}%`,
          height: 160,
          background: "linear-gradient(180deg, transparent, rgba(6, 182, 212, 0.08), transparent)",
          transform: "translateY(-50%)",
        }}
      />
    </AbsoluteFill>
  );
};

const SectionLabel: React.FC<{ children: React.ReactNode; color?: string }> = ({
  children,
  color = OBS_COLORS.cyan,
}) => (
  <div
    style={{
      fontFamily: font,
      color,
      fontSize: 15,
      textTransform: "uppercase",
      letterSpacing: 4,
      fontWeight: 900,
    }}
  >
    {children}
  </div>
);

const MetricCard: React.FC<{
  label: string;
  value: string;
  color: string;
  points: number[];
  delay: number;
  frame: number;
  fps: number;
}> = ({ label, value, color, points, delay, frame, fps }) => {
  const enter = spring({ frame: frame - delay, fps, config: { damping: 16, stiffness: 84 } });
  const opacity = interpolate(frame - delay, [0, 20], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const width = interpolate(frame - delay, [34, 96], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        opacity,
        transform: `translateY(${interpolate(enter, [0, 1], [24, 0])}px)`,
        flex: 1,
        height: 188,
        borderRadius: 22,
        padding: 24,
        background: "rgba(11, 18, 32, 0.72)",
        border: `1px solid ${color}38`,
        boxShadow: `0 20px 70px rgba(0,0,0,0.26), 0 0 42px ${color}12`,
      }}
    >
      <div
        style={{
          fontFamily: font,
          color: OBS_COLORS.dim,
          fontSize: 13,
          letterSpacing: 3,
          textTransform: "uppercase",
          fontWeight: 900,
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontFamily: font,
          color: OBS_COLORS.text,
          fontSize: 50,
          fontWeight: 900,
          marginTop: 12,
        }}
      >
        {value}
      </div>
      <div style={{ display: "flex", alignItems: "end", gap: 9, height: 56, marginTop: 14 }}>
        {points.map((height, index) => (
          <div
            key={index}
            style={{
              width: 26,
              height: height * width,
              borderRadius: 8,
              background: color,
              opacity: 0.45 + index * 0.06,
              boxShadow: `0 0 14px ${color}44`,
            }}
          />
        ))}
      </div>
    </div>
  );
};

const SpinePanel: React.FC<{ frame: number; fps: number }> = ({ frame, fps }) => {
  const services = [
    ["Backend API", "91 ops, 0 failures in last 5min", "1s ago"],
    ["Classifier", "Idle (no recent operations)", "1s ago"],
    ["Admin Agent", "Idle (no recent operations)", "1s ago"],
    ["Investigation Agent", "Idle (no recent operations)", "1s ago"],
    ["Cosmos DB", "Idle (no recent operations)", "0s ago"],
    ["Mobile Capture", "2 ops, 0 failures in last 15min", "0s ago"],
  ];
  const opacity = interpolate(frame, [198, 238], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        flex: 1.15,
        opacity,
        padding: 22,
        borderRadius: 22,
        background: "rgba(5, 9, 18, 0.66)",
        border: "1px solid rgba(63, 185, 80, 0.28)",
      }}
    >
      <div
        style={{
          fontFamily: font,
          color: OBS_COLORS.text,
          fontSize: 25,
          fontWeight: 900,
          marginBottom: 16,
        }}
      >
        Second Brain — Spine
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        {services.map(([name, detail, updated], index) => {
          const enter = spring({
            frame: frame - 235 - index * 14,
            fps,
            config: { damping: 15, stiffness: 94 },
          });
          return (
            <div
              key={name}
              style={{
                opacity: interpolate(frame - 235 - index * 14, [0, 12], [0, 1], {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                }),
                transform: `translateY(${interpolate(enter, [0, 1], [14, 0])}px)`,
                minHeight: 86,
                padding: "15px 16px",
                borderRadius: 14,
                background: "rgba(17, 24, 39, 0.78)",
                border: "1px solid rgba(63, 185, 80, 0.52)",
                fontFamily: font,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                <div style={{ color: OBS_COLORS.text, fontSize: 17, fontWeight: 900 }}>{name}</div>
                <div style={{ color: OBS_COLORS.agent, fontSize: 12, fontWeight: 900 }}>GREEN</div>
              </div>
              <div style={{ color: OBS_COLORS.muted, fontSize: 12, marginTop: 8 }}>{detail}</div>
              <div style={{ color: OBS_COLORS.dim, fontSize: 11, marginTop: 6 }}>{updated}</div>
            </div>
          );
        })}
      </div>
      <div
        style={{
          fontFamily: font,
          color: OBS_COLORS.dim,
          fontSize: 12,
          marginTop: 14,
        }}
      >
        Updated 8:51:57 PM · Freshness 1s · Latency 30ms
      </div>
    </div>
  );
};

const RequestStream: React.FC<{ frame: number; fps: number }> = ({ frame, fps }) => {
  const requests = [
    ["12:04:18.221", "POST /capture", "200", "612ms"],
    ["12:04:18.843", "POST /agents/runs", "200", "418ms"],
    ["12:04:19.271", "POST /tool/file_to_bucket", "200", "44ms"],
    ["12:04:19.339", "POST /admin/route", "200", "307ms"],
    ["12:04:19.668", "PUT /cosmos/captures", "201", "21ms"],
  ];
  const opacity = interpolate(frame, [170, 215], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        opacity,
        flex: 0.85,
        padding: 24,
        borderRadius: 22,
        background: "rgba(5, 9, 18, 0.66)",
        border: "1px solid rgba(88, 166, 255, 0.22)",
      }}
    >
      <div
        style={{
          fontFamily: font,
          color: OBS_COLORS.api,
          fontSize: 14,
          textTransform: "uppercase",
          letterSpacing: 3,
          fontWeight: 900,
          marginBottom: 14,
        }}
      >
        Live request stream
      </div>
      {requests.map(([time, route, code, duration], index) => {
        const rowEnter = spring({
          frame: frame - 210 - index * 26,
          fps,
          config: { damping: 15, stiffness: 90 },
        });
        return (
          <div
            key={`${time}-${route}`}
            style={{
              display: "grid",
              gridTemplateColumns: "116px 1fr 58px 76px",
              gap: 12,
              alignItems: "center",
              height: 48,
              opacity: interpolate(frame - 210 - index * 26, [0, 14], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              }),
              transform: `translateX(${interpolate(rowEnter, [0, 1], [22, 0])}px)`,
              borderTop: index === 0 ? "none" : "1px solid rgba(148, 163, 184, 0.12)",
              fontFamily: mono,
              fontSize: 13,
            }}
          >
            <div style={{ color: OBS_COLORS.dim }}>{time}</div>
            <div style={{ color: OBS_COLORS.text }}>{route}</div>
            <div style={{ color: OBS_COLORS.agent, fontWeight: 900 }}>{code}</div>
            <div style={{ color: OBS_COLORS.muted }}>{duration}</div>
          </div>
        );
      })}
    </div>
  );
};

const DashboardScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const exitOpacity = interpolate(frame, [550, 600], [1, 0.24], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ padding: "70px 100px", opacity: exitOpacity }}>
      <SectionLabel>Application Insights + OpenTelemetry</SectionLabel>
      <div
        style={{
          fontFamily: font,
          color: OBS_COLORS.text,
          fontSize: 60,
          fontWeight: 900,
          marginTop: 10,
        }}
      >
        Distributed tracing across every agent.
      </div>
      <div style={{ display: "flex", gap: 24, marginTop: 44 }}>
        <MetricCard
          label="Requests"
          value="1,284"
          color={OBS_COLORS.api}
          points={[20, 32, 27, 42, 35, 54, 46]}
          delay={44}
          frame={frame}
          fps={fps}
        />
        <MetricCard
          label="Avg Response"
          value="182ms"
          color={OBS_COLORS.agent}
          points={[22, 18, 31, 28, 44, 26, 34]}
          delay={88}
          frame={frame}
          fps={fps}
        />
        <MetricCard
          label="Failed"
          value="0"
          color={OBS_COLORS.danger}
          points={[6, 4, 5, 3, 5, 4, 6]}
          delay={132}
          frame={frame}
          fps={fps}
        />
      </div>
      <div style={{ display: "flex", gap: 24, marginTop: 32, alignItems: "stretch" }}>
        <SpinePanel frame={frame} fps={fps} />
        <RequestStream frame={frame} fps={fps} />
      </div>
    </AbsoluteFill>
  );
};

type WaterfallRow = {
  name: string;
  detail: string;
  ms: number;
  color: string;
  offset: number;
};

const TRACE_ROWS: WaterfallRow[] = [
  { name: "Mobile Capture", detail: "POST /capture", ms: 50, color: OBS_COLORS.api, offset: 0 },
  { name: "API Gateway", detail: "request accepted", ms: 30, color: OBS_COLORS.api, offset: 70 },
  { name: "Orchestrator → Classifier", detail: "GPT call + file_to_bucket", ms: 400, color: OBS_COLORS.agent, offset: 125 },
  { name: "Orchestrator → Admin Agent", detail: "routing + destination assignment", ms: 300, color: OBS_COLORS.agent, offset: 555 },
  { name: "Cosmos DB Write", detail: "document + trace context", ms: 20, color: OBS_COLORS.api, offset: 875 },
];

const SPD_ROWS: WaterfallRow[] = [
  { name: "Mobile Scan", detail: "instrument scan", ms: 50, color: OBS_COLORS.api, offset: 0 },
  { name: "API", detail: "event accepted", ms: 30, color: OBS_COLORS.api, offset: 70 },
  { name: "Compliance Agent", detail: "confidence: 0.97", ms: 400, color: OBS_COLORS.agent, offset: 125 },
  { name: "Routing Agent", detail: "tray-to-OR routing", ms: 300, color: OBS_COLORS.agent, offset: 555 },
  { name: "Cosmos DB Write", detail: "audit evidence stored", ms: 20, color: OBS_COLORS.api, offset: 875 },
];

const Waterfall: React.FC<{
  rows: WaterfallRow[];
  frame: number;
  startFrame: number;
  x: number;
  y: number;
  width: number;
  compact?: boolean;
}> = ({ rows, frame, startFrame, x, y, width, compact = false }) => {
  const rowHeight = compact ? 82 : 96;
  const labelWidth = compact ? 290 : 390;
  const timelineWidth = width - labelWidth - 96;
  const scale = timelineWidth / 920;

  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        width,
        padding: compact ? 22 : 30,
        borderRadius: 24,
        background: "rgba(5, 9, 18, 0.76)",
        border: "1px solid rgba(88, 166, 255, 0.24)",
        boxShadow: "0 28px 90px rgba(0,0,0,0.32)",
      }}
    >
      {rows.map((row, index) => {
        const progress = interpolate(frame - startFrame - index * 20, [0, 48], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        const barLeft = labelWidth + row.offset * scale;
        const barWidth = Math.max(28, row.ms * scale);
        return (
          <div
            key={row.name}
            style={{
              position: "relative",
              height: rowHeight,
              borderTop: index === 0 ? "none" : "1px solid rgba(148, 163, 184, 0.12)",
            }}
          >
            <div
              style={{
                position: "absolute",
                left: 0,
                top: 20,
                fontFamily: font,
                color: OBS_COLORS.text,
                fontSize: compact ? 18 : 22,
                fontWeight: 900,
              }}
            >
              {row.name}
            </div>
            <div
              style={{
                position: "absolute",
                left: 0,
                top: compact ? 48 : 54,
                fontFamily: mono,
                color: OBS_COLORS.muted,
                fontSize: compact ? 12 : 15,
              }}
            >
              {row.detail}
            </div>
            <div
              style={{
                position: "absolute",
                left: labelWidth,
                right: 30,
                top: compact ? 43 : 49,
                height: 1,
                background: "rgba(148, 163, 184, 0.14)",
              }}
            />
            <div
              style={{
                position: "absolute",
                left: barLeft,
                top: compact ? 29 : 33,
                width: barWidth * progress,
                height: compact ? 26 : 32,
                borderRadius: 999,
                background: row.color,
                boxShadow: `0 0 24px ${row.color}44`,
              }}
            />
            <div
              style={{
                position: "absolute",
                left: barLeft + barWidth + 12,
                top: compact ? 33 : 39,
                opacity: progress,
                fontFamily: mono,
                color: row.color,
                fontSize: compact ? 12 : 15,
                fontWeight: 900,
              }}
            >
              {row.ms}ms
            </div>
          </div>
        );
      })}
    </div>
  );
};

const TransactionPathPanel: React.FC<{
  frame: number;
  x: number;
  y: number;
  width: number;
}> = ({ frame, x, y, width }) => {
  const events = [
    ["backend_api", "POST /api/capture", "1ms"],
    ["classifier", "classify_text run=run-1777168391079", "4855ms"],
    ["mobile_capture", "submit_capture", "5792ms"],
    ["admin", "process_capture", "7195ms"],
  ];
  const opacity = interpolate(frame, [120, 165], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        width,
        opacity,
        padding: 24,
        borderRadius: 24,
        background: "rgba(5, 9, 18, 0.76)",
        border: "1px solid rgba(63, 185, 80, 0.28)",
        boxShadow: "0 28px 90px rgba(0,0,0,0.30)",
      }}
    >
      <div
        style={{
          fontFamily: font,
          color: OBS_COLORS.text,
          fontSize: 34,
          fontWeight: 900,
          marginBottom: 14,
        }}
      >
        Transaction Path
      </div>
      <div
        style={{
          fontFamily: mono,
          color: OBS_COLORS.muted,
          fontSize: 13,
          marginBottom: 18,
        }}
      >
        capture c72f32b4-8570-4c71-b398-1fb4a12c362b
      </div>
      {events.map(([name, detail, duration], index) => (
        <div
          key={name}
          style={{
            opacity: interpolate(frame - 170 - index * 22, [0, 14], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            marginBottom: 12,
            padding: "14px 16px",
            borderRadius: 13,
            background: "rgba(17, 24, 39, 0.86)",
            borderLeft: `4px solid ${OBS_COLORS.agent}`,
            fontFamily: font,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", gap: 14 }}>
            <div style={{ color: OBS_COLORS.text, fontSize: 19, fontWeight: 900 }}>{name}</div>
            <div style={{ color: OBS_COLORS.agent, fontSize: 13, fontWeight: 900 }}>SUCCESS</div>
          </div>
          <div style={{ color: OBS_COLORS.muted, fontSize: 13, marginTop: 7 }}>4/25/2026, 8:53 PM · {duration}</div>
          <div style={{ color: OBS_COLORS.text, fontFamily: mono, fontSize: 13, marginTop: 8 }}>{detail}</div>
        </div>
      ))}
      <div style={{ color: OBS_COLORS.dim, fontFamily: font, fontSize: 12, marginTop: 8 }}>
        Optional segments observed: admin.
      </div>
    </div>
  );
};

const BackendHeartbeatPanel: React.FC<{ frame: number }> = ({ frame }) => {
  const opacity = interpolate(frame, [315, 365], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const requests = [
    ["8:52:34 PM", "GET /health", "9ms", "200"],
    ["8:52:29 PM", "GET /health", "12ms", "200"],
    ["8:52:29 PM", "GET /health", "12ms", "200"],
    ["8:52:24 PM", "GET /health", "10ms", "200"],
  ];

  return (
    <div
      style={{
        position: "absolute",
        left: 96,
        right: 96,
        bottom: 54,
        height: 380,
        opacity,
        padding: "22px 26px",
        borderRadius: 24,
        background: "rgba(5, 9, 18, 0.78)",
        border: "1px solid rgba(88, 166, 255, 0.24)",
        boxShadow: "0 24px 80px rgba(0,0,0,0.28)",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start" }}>
        <div>
          <div
            style={{
              fontFamily: font,
              color: OBS_COLORS.dim,
              fontSize: 15,
              fontWeight: 900,
              marginBottom: 8,
            }}
          >
            ← Status board
          </div>
          <div
            style={{
              fontFamily: mono,
              color: OBS_COLORS.text,
              fontSize: 36,
              fontWeight: 900,
            }}
          >
            backend_api
          </div>
        </div>
        <div
          style={{
            fontFamily: font,
            color: OBS_COLORS.api,
            fontSize: 16,
            fontWeight: 900,
            padding: "10px 16px",
            borderRadius: 12,
            background: "rgba(88, 166, 255, 0.14)",
            border: "1px solid rgba(88, 166, 255, 0.34)",
          }}
        >
          Open in native tool ↗
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 0.9fr",
          gap: 28,
          marginTop: 22,
        }}
      >
        <div>
          <div
            style={{
              fontFamily: font,
              color: OBS_COLORS.text,
              fontSize: 24,
              fontWeight: 900,
              marginBottom: 14,
            }}
          >
            Recent transactions
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1.1fr 0.7fr 0.6fr 1.1fr",
              gap: 14,
              padding: "12px 16px",
              background: "rgba(17, 24, 39, 0.86)",
              borderTop: "1px solid rgba(148, 163, 184, 0.22)",
              fontFamily: mono,
              fontSize: 14,
              alignItems: "center",
            }}
          >
            <div style={{ color: OBS_COLORS.muted }}>4/25/2026, 8:53:11 PM</div>
            <div style={{ color: OBS_COLORS.text }}>POST /api/capture</div>
            <div style={{ color: OBS_COLORS.agent, fontWeight: 900 }}>SUCCESS</div>
            <div style={{ color: OBS_COLORS.text }}>1ms</div>
            <div style={{ color: "#9ecbff", textDecoration: "underline" }}>c72f32b4-857...</div>
          </div>
          <div
            style={{
              fontFamily: font,
              color: OBS_COLORS.dim,
              fontSize: 15,
              marginTop: 11,
            }}
          >
            Segment: <span style={{ fontFamily: mono }}>backend_api</span>
          </div>
          <div
            style={{
              fontFamily: font,
              color: OBS_COLORS.text,
              fontSize: 23,
              fontWeight: 900,
              marginTop: 28,
            }}
          >
            Recent exceptions (0)
          </div>
          <div
            style={{
              fontFamily: font,
              color: OBS_COLORS.dim,
              fontSize: 17,
              marginTop: 10,
            }}
          >
            No recent exceptions.
          </div>
        </div>

        <div>
          <div
            style={{
              fontFamily: font,
              color: OBS_COLORS.text,
              fontSize: 24,
              fontWeight: 900,
              marginBottom: 12,
            }}
          >
            Recent requests (200)
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "0.9fr 1.8fr 0.6fr 0.5fr",
              gap: 12,
              padding: "0 12px 10px",
              borderBottom: "1px solid rgba(148, 163, 184, 0.22)",
              fontFamily: font,
              color: OBS_COLORS.text,
              fontSize: 14,
              fontWeight: 900,
            }}
          >
            <div>Time</div>
            <div>Operation</div>
            <div>Duration</div>
            <div>Status</div>
          </div>
          {requests.map(([time, operation, duration, status], index) => (
            <div
              key={`${time}-${index}`}
              style={{
                display: "grid",
                gridTemplateColumns: "0.9fr 1.8fr 0.6fr 0.5fr",
                gap: 12,
                padding: "12px",
                borderBottom: "1px solid rgba(148, 163, 184, 0.11)",
                fontFamily: mono,
                fontSize: 14,
              }}
            >
              <div style={{ color: OBS_COLORS.dim }}>{time}</div>
              <div style={{ color: OBS_COLORS.text }}>
                {operation}
                <div style={{ color: OBS_COLORS.dim, fontSize: 10, marginTop: 4 }}>
                  op=d{index}716a79aca7e608d672a67b848723c6
                </div>
              </div>
              <div style={{ color: OBS_COLORS.text }}>{duration}</div>
              <div style={{ color: OBS_COLORS.text }}>{status}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

const TraceWaterfallScene: React.FC = () => {
  const frame = useCurrentFrame();
  const enter = spring({ frame, fps: 30, config: { damping: 18, stiffness: 72 } });
  const opacity = interpolate(frame, [0, 38], [0, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ padding: "64px 88px" }}>
      <div
        style={{
          opacity,
          transform: `scale(${interpolate(enter, [0, 1], [0.97, 1])})`,
        }}
      >
        <SectionLabel>Trace waterfall</SectionLabel>
        <div
          style={{
            fontFamily: font,
            color: OBS_COLORS.text,
            fontSize: 58,
            fontWeight: 900,
            marginTop: 8,
          }}
        >
          One trace ID follows the full request.
        </div>
        <div
          style={{
            position: "absolute",
            right: 88,
            top: 80,
            fontFamily: mono,
            color: OBS_COLORS.api,
            fontSize: 20,
            padding: "12px 18px",
            borderRadius: 12,
            background: "rgba(88, 166, 255, 0.10)",
            border: "1px solid rgba(88, 166, 255, 0.32)",
          }}
        >
          trace_id=txn_9f42 · total=0.8s
        </div>
      </div>
      <Waterfall
        rows={TRACE_ROWS}
        frame={frame}
        startFrame={88}
        x={86}
        y={252}
        width={1060}
        compact
      />
      <TransactionPathPanel frame={frame} x={1190} y={252} width={640} />
    </AbsoluteFill>
  );
};

const DetailCard: React.FC<{
  title: string;
  color: string;
  lines: Array<[string, string]>;
  frame: number;
  delay: number;
}> = ({ title, color, lines, frame, delay }) => {
  const opacity = interpolate(frame - delay, [0, 24], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        flex: 1,
        opacity,
        padding: 30,
        borderRadius: 24,
        background: "rgba(5, 9, 18, 0.78)",
        border: `1px solid ${color}38`,
        boxShadow: `0 20px 70px rgba(0,0,0,0.30), 0 0 42px ${color}12`,
      }}
    >
      <div
        style={{
          fontFamily: font,
          color,
          fontSize: 14,
          textTransform: "uppercase",
          letterSpacing: 3,
          fontWeight: 900,
          marginBottom: 22,
        }}
      >
        {title}
      </div>
      {lines.map(([label, value]) => (
        <div
          key={label}
          style={{
            display: "grid",
            gridTemplateColumns: "230px 1fr",
            gap: 20,
            padding: "15px 0",
            borderTop: "1px solid rgba(148, 163, 184, 0.13)",
            fontFamily: label === "tool_call" || label === "trace_context" ? mono : font,
          }}
        >
          <div style={{ color: OBS_COLORS.dim, fontSize: 17 }}>{label}</div>
          <div style={{ color: OBS_COLORS.text, fontSize: 21, fontWeight: 800 }}>{value}</div>
        </div>
      ))}
    </div>
  );
};

const DecisionDetailScene: React.FC = () => {
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill style={{ padding: "66px 96px" }}>
      <SectionLabel color={OBS_COLORS.agent}>Decision detail</SectionLabel>
      <div
        style={{
          fontFamily: font,
          color: OBS_COLORS.text,
          fontSize: 56,
          fontWeight: 900,
          marginTop: 8,
        }}
      >
        Every decision is inspectable.
      </div>
      <div style={{ display: "flex", gap: 28, marginTop: 36 }}>
        <DetailCard
          title="Classifier row"
          color={OBS_COLORS.agent}
          frame={frame}
          delay={30}
          lines={[
            ["model", "GPT-4o"],
            ["confidence", "0.85"],
            ["bucket", "Admin"],
            ["tool_call", "file_to_bucket"],
            ["trace_context", "parent_span=span_api_7d21"],
          ]}
        />
        <DetailCard
          title="Admin Agent row"
          color={OBS_COLORS.purple}
          frame={frame}
          delay={165}
          lines={[
            ["routing", "destination assignment"],
            ["Jewel-Osco", "onions, garlic, cilantro, milk"],
            ["CVS", "Tylenol"],
            ["Chewy", "cat food · auto-order evidence"],
            ["trace_context", "parent_span=span_classifier_41b8"],
          ]}
        />
      </div>
      <BackendHeartbeatPanel frame={frame} />
    </AbsoluteFill>
  );
};

const ComplianceScene: React.FC = () => {
  const frame = useCurrentFrame();
  const lensOpacity = interpolate(frame, [70, 130], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const taglineOpacity = interpolate(frame, [360, 455], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ padding: "58px 86px" }}>
      <SectionLabel color={OBS_COLORS.agent}>Compliance lens</SectionLabel>
      <div
        style={{
          fontFamily: font,
          color: OBS_COLORS.text,
          fontSize: 54,
          fontWeight: 900,
          marginTop: 8,
        }}
      >
        Same trace shape. Different operational evidence.
      </div>
      <div
        style={{
          position: "absolute",
          right: 92,
          top: 158,
          opacity: lensOpacity,
          fontFamily: font,
          color: OBS_COLORS.text,
          fontSize: 26,
          fontWeight: 900,
          padding: "16px 22px",
          borderRadius: 16,
          background: "rgba(63, 185, 80, 0.12)",
          border: "1px solid rgba(63, 185, 80, 0.36)",
        }}
      >
        Regulator asks: why was this instrument cleared?
      </div>
      <div
        style={{
          position: "absolute",
          left: 150,
          top: 212,
          width: 1620,
          height: 650,
          opacity: lensOpacity,
          borderRadius: 32,
          border: "2px solid rgba(63, 185, 80, 0.60)",
          boxShadow: "0 0 70px rgba(63, 185, 80, 0.20)",
        }}
      />
      <Waterfall rows={SPD_ROWS} frame={frame} startFrame={110} x={180} y={245} width={1560} />
      <div
        style={{
          position: "absolute",
          left: 160,
          right: 160,
          bottom: 58,
          opacity: taglineOpacity,
          fontFamily: font,
          color: OBS_COLORS.text,
          fontSize: 31,
          fontWeight: 900,
          textAlign: "center",
          padding: "18px 28px",
          borderRadius: 18,
          background: "rgba(5, 9, 18, 0.78)",
          border: "1px solid rgba(63, 185, 80, 0.36)",
        }}
      >
        Every decision. Every model. Every timestamp. That's not a log file — that's evidence.
      </div>
    </AbsoluteFill>
  );
};

export const BreakoutObservabilityVideo: React.FC = () => (
  <>
    <Background />
    <Audio src={staticFile("observability.mp3")} />
    <Sequence from={OBS_SCENES.dashboard.start} durationInFrames={OBS_SCENES.dashboard.duration}>
      <DashboardScene />
    </Sequence>
    <Sequence from={OBS_SCENES.waterfall.start} durationInFrames={OBS_SCENES.waterfall.duration}>
      <TraceWaterfallScene />
    </Sequence>
    <Sequence from={OBS_SCENES.detail.start} durationInFrames={OBS_SCENES.detail.duration}>
      <DecisionDetailScene />
    </Sequence>
    <Sequence from={OBS_SCENES.compliance.start} durationInFrames={OBS_SCENES.compliance.duration}>
      <ComplianceScene />
    </Sequence>
  </>
);

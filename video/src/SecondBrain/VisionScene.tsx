import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  interpolate,
  spring,
  useVideoConfig,
} from "remotion";
import { COLORS } from "./constants";

const AgentNode: React.FC<{
  name: string;
  icon: string;
  color: string;
  x: number;
  y: number;
  delay: number;
  frame: number;
  fps: number;
  isActive?: boolean;
  description: string;
}> = ({ name, icon, color, x, y, delay, frame, fps, isActive, description }) => {
  const entrance = spring({
    frame: frame - delay,
    fps,
    config: { damping: 12, stiffness: 80 },
  });
  const opacity = interpolate(frame - delay, [0, 15], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Pulse for active agents
  const pulseScale = isActive
    ? 1 + Math.sin(frame * 0.08) * 0.03
    : 1;

  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        opacity,
        transform: `scale(${entrance * pulseScale})`,
        textAlign: "center",
      }}
    >
      <div
        style={{
          width: 100,
          height: 100,
          borderRadius: 24,
          background: isActive
            ? `linear-gradient(135deg, ${color}40, ${color}20)`
            : `${color}15`,
          border: `2px solid ${isActive ? color : `${color}40`}`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 44,
          margin: "0 auto",
          boxShadow: isActive ? `0 0 30px ${color}25` : "none",
        }}
      >
        {icon}
      </div>
      <div
        style={{
          fontFamily: "SF Pro Display, -apple-system, sans-serif",
          fontSize: 20,
          fontWeight: 600,
          color: isActive ? COLORS.textWhite : COLORS.textGray,
          marginTop: 12,
        }}
      >
        {name}
      </div>
      <div
        style={{
          fontFamily: "SF Pro Display, -apple-system, sans-serif",
          fontSize: 15,
          color: COLORS.textDim,
          marginTop: 4,
          maxWidth: 140,
        }}
      >
        {description}
      </div>
    </div>
  );
};

const ConnectionLine: React.FC<{
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  delay: number;
  frame: number;
  active?: boolean;
  color: string;
}> = ({ x1, y1, x2, y2, delay, frame, active, color }) => {
  const progress = interpolate(frame - delay, [0, 20], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <svg
      style={{ position: "absolute", inset: 0, pointerEvents: "none" }}
      viewBox="0 0 1920 1080"
    >
      <line
        x1={x1}
        y1={y1}
        x2={x1 + (x2 - x1) * progress}
        y2={y1 + (y2 - y1) * progress}
        stroke={active ? color : `${color}30`}
        strokeWidth={active ? 2.5 : 1.5}
        strokeDasharray={active ? "none" : "8 6"}
      />
    </svg>
  );
};

export const VisionScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleOpacity = interpolate(frame, [0, 25], [0, 1], {
    extrapolateRight: "clamp",
  });

  // 870 frame duration
  const exitOpacity = interpolate(frame, [830, 870], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Center point for the hub
  const hubX = 960;
  const hubY = 520;

  return (
    <AbsoluteFill style={{ padding: "80px 120px", opacity: exitOpacity }}>
      {/* Section label */}
      <div style={{ opacity: titleOpacity }}>
        <span
          style={{
            fontFamily: "SF Mono, monospace",
            fontSize: 18,
            color: COLORS.accentCyan,
            textTransform: "uppercase",
            letterSpacing: 4,
          }}
        >
          02 — The Multi-Agent Vision
        </span>
        <h2
          style={{
            fontFamily: "SF Pro Display, -apple-system, sans-serif",
            fontSize: 56,
            fontWeight: 700,
            color: COLORS.textWhite,
            margin: "12px 0 0 0",
            lineHeight: 1.1,
          }}
        >
          A Team of{" "}
          <span
            style={{
              background: `linear-gradient(135deg, ${COLORS.accentPurple}, ${COLORS.accentBlue})`,
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            Specialist Agents
          </span>
        </h2>
      </div>

      {/* Connection lines */}
      <ConnectionLine
        x1={hubX + 50}
        y1={hubY}
        x2={340}
        y2={370}
        delay={120}
        frame={frame}
        active
        color={COLORS.accentBlue}
      />
      <ConnectionLine
        x1={hubX + 50}
        y1={hubY}
        x2={340}
        y2={580}
        delay={180}
        frame={frame}
        active
        color={COLORS.accentPink}
      />
      <ConnectionLine
        x1={hubX + 50}
        y1={hubY}
        x2={1520}
        y2={370}
        delay={420}
        frame={frame}
        color={COLORS.accentGreen}
      />
      <ConnectionLine
        x1={hubX + 50}
        y1={hubY}
        x2={1520}
        y2={580}
        delay={480}
        frame={frame}
        color={COLORS.accentOrange}
      />
      <ConnectionLine
        x1={hubX + 50}
        y1={hubY}
        x2={1520}
        y2={770}
        delay={540}
        frame={frame}
        color={COLORS.accentCyan}
      />

      {/* Central hub: Code-Based Router */}
      <AgentNode
        name="FastAPI Router"
        icon="🔀"
        color={COLORS.textWhite}
        x={hubX - 50}
        y={hubY - 70}
        delay={60}
        frame={frame}
        fps={fps}
        isActive
        description="Code-based routing"
      />

      {/* Active agents (left side) */}
      <AgentNode
        name="Classifier"
        icon="🏷"
        color={COLORS.accentBlue}
        x={220}
        y={300}
        delay={100}
        frame={frame}
        fps={fps}
        isActive
        description="Routes captures"
      />
      <AgentNode
        name="Admin Agent"
        icon="🛒"
        color={COLORS.accentPink}
        x={220}
        y={510}
        delay={160}
        frame={frame}
        fps={fps}
        isActive
        description="Shopping lists"
      />

      {/* "LIVE" badge */}
      <div
        style={{
          position: "absolute",
          left: 160,
          top: 260,
          opacity: interpolate(frame, [200, 230], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        <div
          style={{
            fontFamily: "SF Mono, monospace",
            fontSize: 13,
            color: COLORS.accentGreen,
            background: `${COLORS.accentGreen}18`,
            border: `1px solid ${COLORS.accentGreen}40`,
            borderRadius: 6,
            padding: "3px 10px",
          }}
        >
          LIVE
        </div>
      </div>

      {/* Future agents (right side) */}
      <AgentNode
        name="Projects Agent"
        icon="📋"
        color={COLORS.accentGreen}
        x={1400}
        y={300}
        delay={400}
        frame={frame}
        fps={fps}
        description="Action tracking"
      />
      <AgentNode
        name="Ideas Agent"
        icon="💡"
        color={COLORS.accentOrange}
        x={1400}
        y={510}
        delay={460}
        frame={frame}
        fps={fps}
        description="Weekly check-ins"
      />
      <AgentNode
        name="People Agent"
        icon="👥"
        color={COLORS.accentCyan}
        x={1400}
        y={700}
        delay={520}
        frame={frame}
        fps={fps}
        description="Relationship nudges"
      />

      {/* "PLANNED" badge */}
      <div
        style={{
          position: "absolute",
          right: 200,
          top: 260,
          opacity: interpolate(frame, [550, 580], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        <div
          style={{
            fontFamily: "SF Mono, monospace",
            fontSize: 13,
            color: COLORS.textDim,
            background: `${COLORS.textDim}18`,
            border: `1px solid ${COLORS.textDim}40`,
            borderRadius: 6,
            padding: "3px 10px",
          }}
        >
          PLANNED
        </div>
      </div>

      {/* Foundry badge at bottom */}
      <div
        style={{
          position: "absolute",
          bottom: 80,
          left: "50%",
          transform: "translateX(-50%)",
          opacity: interpolate(frame, [600, 640], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
        }}
      >
        <div
          style={{
            fontFamily: "SF Mono, monospace",
            fontSize: 18,
            color: COLORS.textDim,
            textAlign: "center",
          }}
        >
          Powered by{" "}
          <span style={{ color: COLORS.accentBlue }}>
            Azure AI Foundry Agent Service
          </span>{" "}
          + <span style={{ color: COLORS.accentPurple }}>GPT-4o</span>
        </div>
      </div>
    </AbsoluteFill>
  );
};

import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { BUILT_AGENTS, COLORS, DEVELOPMENT_AGENTS } from "./constants";

type Agent = (typeof BUILT_AGENTS)[number] | (typeof DEVELOPMENT_AGENTS)[number];

const GREEN = "#3fb950";
const AMBER = "#d29922";
const HUB = "#58a6ff";

const TraceIcon: React.FC = () => (
  <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
    {[0, 1, 2].map((i) => (
      <div
        key={i}
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: COLORS.accentCyan,
          boxShadow: `0 0 10px ${COLORS.accentCyan}88`,
        }}
      />
    ))}
  </div>
);

const ChartIcon: React.FC = () => (
  <div style={{ display: "flex", alignItems: "end", gap: 4, height: 22 }}>
    {[10, 16, 22].map((height, i) => (
      <div
        key={i}
        style={{
          width: 7,
          height,
          borderRadius: 4,
          background: COLORS.accentGreen,
          boxShadow: `0 0 10px ${COLORS.accentGreen}66`,
        }}
      />
    ))}
  </div>
);

const AgentCard: React.FC<{
  agent: Agent;
  delay: number;
  x: number;
  y: number;
  width: number;
  status: "built" | "development";
  frame: number;
  fps: number;
  hub?: boolean;
}> = ({ agent, delay, x, y, width, status, frame, fps, hub }) => {
  const entrance = spring({
    frame: frame - delay,
    fps,
    config: { damping: 16, stiffness: 88 },
  });
  const opacity = interpolate(frame - delay, [0, 18], [0, status === "built" ? 1 : 0.58], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const translateY = interpolate(entrance, [0, 1], [26, 0]);
  const statusColor = status === "built" ? GREEN : AMBER;
  const borderColor = hub ? HUB : status === "built" ? agent.color : AMBER;

  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        width,
        minHeight: hub ? 154 : 132,
        opacity,
        transform: `translateY(${translateY}px) scale(${hub ? 1.05 : 1})`,
        padding: "22px 24px",
        borderRadius: 20,
        background:
          status === "built"
            ? "linear-gradient(135deg, rgba(15, 23, 42, 0.92), rgba(5, 9, 18, 0.82))"
            : "linear-gradient(135deg, rgba(30, 41, 59, 0.48), rgba(15, 23, 42, 0.44))",
        border: `2px solid ${borderColor}${hub ? "aa" : "55"}`,
        boxShadow: hub
          ? `0 0 45px ${HUB}22, 0 24px 70px rgba(0,0,0,0.28)`
          : "0 18px 52px rgba(0, 0, 0, 0.22)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <div
          style={{
            width: 12,
            height: 12,
            borderRadius: "50%",
            background: statusColor,
            boxShadow: `0 0 16px ${statusColor}99`,
            flexShrink: 0,
          }}
        />
        <div
          style={{
            fontFamily: "Arial, sans-serif",
            fontSize: hub ? 30 : 25,
            fontWeight: 900,
            color: status === "built" ? COLORS.textWhite : COLORS.textGray,
          }}
        >
          {agent.name}
        </div>
      </div>

      <div
        style={{
          fontFamily: "Arial, sans-serif",
          fontSize: 16,
          color: status === "built" ? COLORS.textGray : COLORS.textDim,
          marginTop: 12,
          lineHeight: 1.35,
        }}
      >
        {agent.role}
      </div>

      {agent.name === "Investigation Agent" && (
        <div style={{ display: "flex", gap: 12, marginTop: 14 }}>
          <div
            style={{
              width: 42,
              height: 34,
              borderRadius: 10,
              border: `1px solid ${COLORS.accentCyan}44`,
              background: `${COLORS.accentCyan}12`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <TraceIcon />
          </div>
          <div
            style={{
              width: 42,
              height: 34,
              borderRadius: 10,
              border: `1px solid ${COLORS.accentGreen}44`,
              background: `${COLORS.accentGreen}12`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <ChartIcon />
          </div>
        </div>
      )}

      {status === "development" && (
        <div
          style={{
            position: "absolute",
            right: 18,
            top: 18,
            color: AMBER,
            fontFamily: "Arial, sans-serif",
            fontSize: 11,
            fontWeight: 900,
            letterSpacing: 1.8,
            textTransform: "uppercase",
          }}
        >
          in development
        </div>
      )}
    </div>
  );
};

export const AgentPanelScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleOpacity = interpolate(frame, [0, 24], [0, 1], {
    extrapolateRight: "clamp",
  });
  const exitOpacity = interpolate(frame, [1350, 1395], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ padding: "58px 96px", opacity: exitOpacity }}>
      <div style={{ opacity: titleOpacity, textAlign: "center" }}>
        <div
          style={{
            fontFamily: "Arial, sans-serif",
            fontSize: 15,
            color: COLORS.accentCyan,
            textTransform: "uppercase",
            letterSpacing: 4,
            fontWeight: 900,
          }}
        >
          Azure AI Foundry
        </div>
        <div
          style={{
            fontFamily: "Arial, sans-serif",
            fontSize: 64,
            fontWeight: 900,
            color: COLORS.textWhite,
            marginTop: 8,
          }}
        >
          Agent roster
        </div>
      </div>

      <AgentCard
        agent={BUILT_AGENTS[0]}
        delay={45}
        x={700}
        y={245}
        width={520}
        status="built"
        frame={frame}
        fps={fps}
        hub
      />
      <AgentCard
        agent={BUILT_AGENTS[1]}
        delay={245}
        x={170}
        y={450}
        width={480}
        status="built"
        frame={frame}
        fps={fps}
      />
      <AgentCard
        agent={BUILT_AGENTS[2]}
        delay={430}
        x={720}
        y={510}
        width={480}
        status="built"
        frame={frame}
        fps={fps}
      />
      <AgentCard
        agent={BUILT_AGENTS[3]}
        delay={620}
        x={1270}
        y={450}
        width={480}
        status="built"
        frame={frame}
        fps={fps}
      />

      {DEVELOPMENT_AGENTS.map((agent, index) => (
        <AgentCard
          key={agent.name}
          agent={agent}
          delay={850 + index * 100}
          x={255 + index * 455}
          y={825}
          width={410}
          status="development"
          frame={frame}
          fps={fps}
        />
      ))}
    </AbsoluteFill>
  );
};

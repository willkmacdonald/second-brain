import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import {
  COLORS,
  SECOND_BRAIN_CHAIN,
  SECOND_BRAIN_INDEPENDENT,
  SPD_AGENTS,
  SPD_INDEPENDENT,
} from "./constants";

type FlowNode = {
  name: string;
  role: string;
  color: string;
};

type TokenType = "voice" | "cycle";

const STATUS_GREEN = "#3fb950";

const Token: React.FC<{ type: TokenType; color: string }> = ({ type, color }) => (
  <div
    style={{
      width: 38,
      height: 38,
      borderRadius: 13,
      background: `${color}18`,
      border: `1px solid ${color}66`,
      boxShadow: `0 0 18px ${color}44`,
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
    }}
  >
    {type === "voice" ? (
      <div
        style={{
          width: 9,
          height: 19,
          borderRadius: 8,
          border: `2px solid ${color}`,
        }}
      />
    ) : (
      <div
        style={{
          width: 18,
          height: 18,
          borderRadius: "50%",
          border: `2px solid ${color}`,
          position: "relative",
        }}
      >
        <div
          style={{
            position: "absolute",
            left: "50%",
            top: -6,
            width: 2,
            height: 28,
            background: color,
            transform: "translateX(-50%)",
          }}
        />
      </div>
    )}
  </div>
);

const ClockChip: React.FC<{
  name: string;
  role: string;
  frame: number;
  delay: number;
}> = ({ name, role, frame, delay }) => {
  const pulse = interpolate((frame + delay) % 82, [0, 41, 82], [0.25, 1, 0.25], {
    extrapolateRight: "clamp",
  });
  const angle = interpolate((frame + delay) % 90, [0, 90], [0, 360]);

  return (
    <div
      style={{
        flex: 1,
        minHeight: 98,
        padding: "18px 18px",
        borderRadius: 16,
        background: "rgba(210, 153, 34, 0.08)",
        border: "1px solid rgba(210, 153, 34, 0.34)",
        boxShadow: `0 0 ${12 + pulse * 16}px rgba(210, 153, 34, 0.16)`,
        display: "flex",
        alignItems: "center",
        gap: 14,
      }}
    >
      <div
        style={{
          width: 30,
          height: 30,
          borderRadius: "50%",
          border: `2px solid ${COLORS.accentOrange}`,
          position: "relative",
          flexShrink: 0,
        }}
      >
        <div
          style={{
            position: "absolute",
            left: "50%",
            top: "50%",
            width: 2,
            height: 11,
            background: COLORS.accentOrange,
            transformOrigin: "50% 0%",
            transform: `rotate(${angle}deg) translate(-50%, 0)`,
          }}
        />
      </div>
      <div>
        <div
          style={{
            fontFamily: "Arial, sans-serif",
            color: COLORS.textWhite,
            fontSize: 18,
            fontWeight: 900,
          }}
        >
          {name}
        </div>
        <div
          style={{
            fontFamily: "Arial, sans-serif",
            color: COLORS.textDim,
            fontSize: 13,
            marginTop: 5,
            lineHeight: 1.25,
          }}
        >
          {role}
        </div>
      </div>
    </div>
  );
};

const DomainPanel: React.FC<{
  title: string;
  label: string;
  nodes: readonly FlowNode[];
  independent: readonly FlowNode[];
  tokenType: TokenType;
  tokenLabel: string;
  result: string;
  accent: string;
  x: number;
  y: number;
  width: number;
  frame: number;
  fps: number;
  delay: number;
}> = ({
  title,
  label,
  nodes,
  independent,
  tokenType,
  tokenLabel,
  result,
  accent,
  x,
  y,
  width,
  frame,
  fps,
  delay,
}) => {
  const opacity = interpolate(frame - delay, [0, 28], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const scale = spring({
    frame: frame - delay,
    fps,
    config: { damping: 17, stiffness: 80 },
  });
  const activeIndex = Math.min(
    nodes.length - 1,
    Math.floor(
      interpolate(frame - delay, [120, 560], [0, nodes.length], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    )
  );
  const nodeSize = 92;
  const usable = width - 126;
  const gap = (usable - nodes.length * nodeSize) / (nodes.length - 1);
  const startX = 38;
  const flowY = 310;
  const tokenX = interpolate(
    frame - delay,
    [110, 565],
    [startX - 45, startX + (nodes.length - 1) * (nodeSize + gap) + nodeSize + 52],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const tokenOpacity = interpolate(frame - delay, [85, 110], [0, 1], {
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
        height: 650,
        opacity,
        transform: `scale(${interpolate(scale, [0, 1], [0.985, 1])})`,
        borderRadius: 28,
        background: "rgba(5, 9, 18, 0.66)",
        border: `1px solid ${accent}32`,
        boxShadow: "inset 0 1px 0 rgba(255,255,255,0.05)",
        padding: 30,
      }}
    >
      <div
        style={{
          fontFamily: "Arial, sans-serif",
          fontSize: 13,
          color: accent,
          fontWeight: 900,
          letterSpacing: 3,
          textTransform: "uppercase",
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontFamily: "Arial, sans-serif",
          fontSize: 40,
          fontWeight: 900,
          color: COLORS.textWhite,
          marginTop: 8,
        }}
      >
        {title}
      </div>

      <div
        style={{
          position: "absolute",
          left: 30,
          right: 30,
          top: 170,
          height: 285,
        }}
      >
        {nodes.map((node, index) => {
          const nodeX = startX + index * (nodeSize + gap);
          const isActive = activeIndex === index;
          const isPast = index < activeIndex;
          return (
            <div
              key={node.name}
              style={{
                position: "absolute",
                left: nodeX,
                top: flowY - 170,
                width: nodeSize,
                minHeight: 132,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
              }}
            >
              <div
                style={{
                  width: nodeSize,
                  height: nodeSize,
                  borderRadius: 22,
                  background: isActive ? `${node.color}22` : "rgba(30, 41, 59, 0.72)",
                  border: `2px solid ${node.color}${isActive ? "99" : isPast ? "66" : "38"}`,
                  boxShadow: isActive ? `0 0 30px ${node.color}44` : "none",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  textAlign: "center",
                  color: isActive ? node.color : COLORS.textGray,
                  fontFamily: "Arial, sans-serif",
                  fontSize: 12,
                  fontWeight: 900,
                  lineHeight: 1.08,
                  padding: 9,
                  position: "relative",
                }}
              >
                <div
                  style={{
                    position: "absolute",
                    right: 9,
                    top: 9,
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    background: STATUS_GREEN,
                    boxShadow: `0 0 10px ${STATUS_GREEN}`,
                  }}
                />
                {node.name}
              </div>
              <div
                style={{
                  marginTop: 9,
                  color: COLORS.textDim,
                  fontFamily: "Arial, sans-serif",
                  fontSize: 12,
                  lineHeight: 1.2,
                  textAlign: "center",
                  width: 124,
                }}
              >
                {node.role}
              </div>
            </div>
          );
        })}

        {nodes.slice(0, -1).map((_, index) => {
          const x1 = startX + index * (nodeSize + gap) + nodeSize;
          const x2 = startX + (index + 1) * (nodeSize + gap);
          const isActive = index < activeIndex;
          const isPulsing = index === activeIndex - 1;
          const pulse = interpolate(frame % 42, [0, 42], [0, 1], {
            extrapolateRight: "clamp",
          });
          return (
            <div
              key={index}
              style={{
                position: "absolute",
                left: x1,
                top: flowY - 124,
                width: x2 - x1,
                height: 2,
                background: isActive ? `${COLORS.accentCyan}66` : `${COLORS.textDim}30`,
              }}
            >
              {isPulsing && (
                <div
                  style={{
                    position: "absolute",
                    left: `${pulse * 100}%`,
                    top: -4,
                    width: 10,
                    height: 10,
                    borderRadius: "50%",
                    background: COLORS.accentCyan,
                    boxShadow: `0 0 14px ${COLORS.accentCyan}`,
                    transform: "translateX(-50%)",
                  }}
                />
              )}
            </div>
          );
        })}

        <div
          style={{
            position: "absolute",
            left: tokenX,
            top: flowY - 142,
            transform: "translate(-50%, -50%)",
            opacity: tokenOpacity,
          }}
        >
          <Token type={tokenType} color={accent} />
        </div>
        <div
          style={{
            position: "absolute",
            left: 36,
            top: 82,
            color: COLORS.textDim,
            fontFamily: "Arial, sans-serif",
            fontSize: 13,
          }}
        >
          {tokenLabel}
        </div>
        <div
          style={{
            position: "absolute",
            right: 20,
            top: 206,
            opacity: interpolate(frame - delay, [580, 640], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            color: COLORS.accentGreen,
            fontFamily: "Arial, sans-serif",
            fontSize: 15,
            fontWeight: 900,
            padding: "8px 13px",
            borderRadius: 11,
            background: `${COLORS.accentGreen}10`,
            border: `1px solid ${COLORS.accentGreen}30`,
          }}
        >
          {result}
        </div>
      </div>

      {independent.length > 0 && (
        <div
          style={{
            position: "absolute",
            left: 30,
            right: 30,
            bottom: 34,
          }}
        >
          <div
            style={{
              color: COLORS.accentOrange,
              fontFamily: "Arial, sans-serif",
              fontSize: 13,
              fontWeight: 900,
              textTransform: "uppercase",
              letterSpacing: 2.4,
              marginBottom: 12,
            }}
          >
            Independent schedule
          </div>
          <div style={{ display: "flex", gap: 13 }}>
            {independent.map((node, index) => (
              <ClockChip
                key={node.name}
                name={node.name}
                role={node.role}
                frame={frame}
                delay={index * 20}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export const SplitScreenScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleOpacity = interpolate(frame, [0, 30], [0, 1], {
    extrapolateRight: "clamp",
  });
  const barOpacity = interpolate(frame, [745, 820], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ padding: "48px 70px" }}>
      <div style={{ textAlign: "center", opacity: titleOpacity }}>
        <div
          style={{
            fontFamily: "Arial, sans-serif",
            fontSize: 15,
            color: COLORS.accentOrange,
            textTransform: "uppercase",
            letterSpacing: 4,
            fontWeight: 900,
          }}
        >
          Same patterns, different domain
        </div>
        <div
          style={{
            fontFamily: "Arial, sans-serif",
            fontSize: 52,
            fontWeight: 900,
            color: COLORS.textWhite,
            marginTop: 8,
          }}
        >
          Personal agents become sterile processing agents.
        </div>
      </div>

      <DomainPanel
        title="Second Brain"
        label="Personal intelligence"
        nodes={SECOND_BRAIN_CHAIN}
        independent={SECOND_BRAIN_INDEPENDENT}
        tokenType="voice"
        tokenLabel="voice note"
        result="Filed → Projects"
        accent={COLORS.accentCyan}
        x={70}
        y={230}
        width={860}
        frame={frame}
        fps={fps}
        delay={40}
      />

      <DomainPanel
        title="Sterile Processing"
        label="SPD equivalent"
        nodes={SPD_AGENTS}
        independent={SPD_INDEPENDENT}
        tokenType="cycle"
        tokenLabel="sterilizer cycle"
        result="Compliance checked → Routed"
        accent={COLORS.accentOrange}
        x={990}
        y={230}
        width={860}
        frame={frame}
        fps={fps}
        delay={170}
      />

      <div
        style={{
          position: "absolute",
          left: 220,
          right: 220,
          bottom: 44,
          height: 66,
          opacity: barOpacity,
          borderRadius: 18,
          background: "linear-gradient(90deg, rgba(88,166,255,0.18), rgba(6,182,212,0.22), rgba(210,153,34,0.18))",
          border: "1px solid rgba(148, 163, 184, 0.24)",
          boxShadow: "0 0 42px rgba(6, 182, 212, 0.16)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "Arial, sans-serif",
          color: COLORS.textWhite,
          fontSize: 26,
          fontWeight: 900,
          letterSpacing: 0.3,
        }}
      >
        Azure AI Foundry
      </div>
    </AbsoluteFill>
  );
};

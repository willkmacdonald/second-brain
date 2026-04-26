import React from "react";
import { AbsoluteFill, useCurrentFrame, interpolate, spring, useVideoConfig } from "remotion";
import { COLORS } from "./constants";

const BrainIcon: React.FC<{ scale: number; opacity: number }> = ({
  scale,
  opacity,
}) => (
  <div
    style={{
      opacity,
      transform: `scale(${scale})`,
      fontSize: 120,
      lineHeight: 1,
      marginBottom: 40,
    }}
  >
    🧠
  </div>
);

export const IntroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Brain icon entrance
  const brainScale = spring({ frame, fps, config: { damping: 12, stiffness: 80 } });
  const brainOpacity = interpolate(frame, [0, 20], [0, 1], {
    extrapolateRight: "clamp",
  });

  // Title entrance (staggered)
  const titleY = interpolate(frame, [15, 45], [60, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const titleOpacity = interpolate(frame, [15, 45], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Subtitle entrance
  const subtitleOpacity = interpolate(frame, [50, 75], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const subtitleY = interpolate(frame, [50, 75], [30, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Tagline
  const taglineOpacity = interpolate(frame, [120, 160], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Exit fade (420 frame duration)
  const exitOpacity = interpolate(frame, [380, 420], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        opacity: exitOpacity,
      }}
    >
      <BrainIcon scale={brainScale} opacity={brainOpacity} />

      <div
        style={{
          transform: `translateY(${titleY}px)`,
          opacity: titleOpacity,
          textAlign: "center",
        }}
      >
        <h1
          style={{
            fontFamily: "SF Pro Display, -apple-system, sans-serif",
            fontSize: 90,
            fontWeight: 700,
            color: COLORS.textWhite,
            margin: 0,
            letterSpacing: -2,
          }}
        >
          The Active{" "}
          <span
            style={{
              background: `linear-gradient(135deg, ${COLORS.accentBlue}, ${COLORS.accentPurple})`,
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            Second Brain
          </span>
        </h1>
      </div>

      <div
        style={{
          transform: `translateY(${subtitleY}px)`,
          opacity: subtitleOpacity,
          marginTop: 24,
        }}
      >
        <p
          style={{
            fontFamily: "SF Pro Display, -apple-system, sans-serif",
            fontSize: 36,
            fontWeight: 400,
            color: COLORS.textGray,
            margin: 0,
          }}
        >
          AI-Powered Capture & Intelligence System
        </p>
      </div>

      <div style={{ opacity: taglineOpacity, marginTop: 40 }}>
        <div
          style={{
            fontFamily: "SF Mono, monospace",
            fontSize: 22,
            color: COLORS.accentCyan,
            padding: "12px 28px",
            border: `1px solid ${COLORS.accentCyan}40`,
            borderRadius: 8,
            background: `${COLORS.accentCyan}08`,
          }}
        >
          Built on Azure AI Foundry + Microsoft Agent Framework
        </div>
      </div>
    </AbsoluteFill>
  );
};

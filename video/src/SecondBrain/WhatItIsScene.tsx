import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  interpolate,
  spring,
  useVideoConfig,
} from "remotion";
import { COLORS } from "./constants";

const ProblemCard: React.FC<{
  text: string;
  delay: number;
  frame: number;
  fps: number;
}> = ({ text, delay, frame, fps }) => {
  const entrance = spring({
    frame: frame - delay,
    fps,
    config: { damping: 14, stiffness: 100 },
  });
  const opacity = interpolate(frame - delay, [0, 15], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        opacity,
        transform: `translateX(${interpolate(entrance, [0, 1], [-40, 0])}px)`,
        display: "flex",
        alignItems: "center",
        gap: 16,
        marginBottom: 20,
      }}
    >
      <div
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: COLORS.accentPink,
          flexShrink: 0,
        }}
      />
      <span
        style={{
          fontFamily: "SF Pro Display, -apple-system, sans-serif",
          fontSize: 30,
          color: COLORS.textGray,
        }}
      >
        {text}
      </span>
    </div>
  );
};

const SolutionPoint: React.FC<{
  icon: string;
  text: string;
  delay: number;
  frame: number;
  fps: number;
}> = ({ icon, text, delay, frame, fps }) => {
  const entrance = spring({
    frame: frame - delay,
    fps,
    config: { damping: 12, stiffness: 90 },
  });
  const opacity = interpolate(frame - delay, [0, 15], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        opacity,
        transform: `scale(${entrance})`,
        display: "flex",
        alignItems: "center",
        gap: 20,
        marginBottom: 24,
      }}
    >
      <div
        style={{
          width: 56,
          height: 56,
          borderRadius: 14,
          background: `linear-gradient(135deg, ${COLORS.accentBlue}30, ${COLORS.accentPurple}30)`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 28,
          flexShrink: 0,
        }}
      >
        {icon}
      </div>
      <span
        style={{
          fontFamily: "SF Pro Display, -apple-system, sans-serif",
          fontSize: 30,
          color: COLORS.textWhite,
          fontWeight: 500,
        }}
      >
        {text}
      </span>
    </div>
  );
};

export const WhatItIsScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Scene title
  const titleOpacity = interpolate(frame, [0, 25], [0, 1], {
    extrapolateRight: "clamp",
  });

  // Transition from problem to solution
  const problemOpacity = interpolate(frame, [350, 400], [1, 0.3], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Exit (690 frame duration)
  const exitOpacity = interpolate(frame, [650, 690], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        padding: "80px 120px",
        opacity: exitOpacity,
      }}
    >
      {/* Section label */}
      <div style={{ opacity: titleOpacity, marginBottom: 50 }}>
        <span
          style={{
            fontFamily: "SF Mono, monospace",
            fontSize: 18,
            color: COLORS.accentCyan,
            textTransform: "uppercase",
            letterSpacing: 4,
          }}
        >
          01 — The Problem & Solution
        </span>
        <h2
          style={{
            fontFamily: "SF Pro Display, -apple-system, sans-serif",
            fontSize: 64,
            fontWeight: 700,
            color: COLORS.textWhite,
            margin: "12px 0 0 0",
            lineHeight: 1.1,
          }}
        >
          Your brain is for thinking,
          <br />
          <span style={{ color: COLORS.accentBlue }}>not storage.</span>
        </h2>
      </div>

      <div style={{ display: "flex", gap: 80 }}>
        {/* Problem side */}
        <div style={{ flex: 1, opacity: problemOpacity }}>
          <h3
            style={{
              fontFamily: "SF Pro Display, -apple-system, sans-serif",
              fontSize: 28,
              fontWeight: 600,
              color: COLORS.accentPink,
              marginBottom: 30,
              marginTop: 0,
            }}
          >
            The Problem
          </h3>
          <ProblemCard
            text="Notes require organizing at capture time"
            delay={60}
            frame={frame}
            fps={fps}
          />
          <ProblemCard
            text="Open cognitive loops pile up"
            delay={100}
            frame={frame}
            fps={fps}
          />
          <ProblemCard
            text="Important thoughts slip away"
            delay={140}
            frame={frame}
            fps={fps}
          />
          <ProblemCard
            text="Existing tools are passive storage"
            delay={180}
            frame={frame}
            fps={fps}
          />
        </div>

        {/* Solution side */}
        <div style={{ flex: 1 }}>
          <h3
            style={{
              fontFamily: "SF Pro Display, -apple-system, sans-serif",
              fontSize: 28,
              fontWeight: 600,
              color: COLORS.accentGreen,
              marginBottom: 30,
              marginTop: 0,
            }}
          >
            The Solution
          </h3>
          <SolutionPoint
            icon="🎙"
            text="One-tap voice or text capture"
            delay={280}
            frame={frame}
            fps={fps}
          />
          <SolutionPoint
            icon="🤖"
            text="AI agents classify automatically"
            delay={330}
            frame={frame}
            fps={fps}
          />
          <SolutionPoint
            icon="📂"
            text="Four smart buckets: People, Projects, Ideas, Admin"
            delay={380}
            frame={frame}
            fps={fps}
          />
          <SolutionPoint
            icon="✅"
            text="Zero organizational effort from you"
            delay={430}
            frame={frame}
            fps={fps}
          />
        </div>
      </div>
    </AbsoluteFill>
  );
};

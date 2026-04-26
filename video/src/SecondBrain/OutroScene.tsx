import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  interpolate,
  spring,
  useVideoConfig,
} from "remotion";
import { COLORS } from "./constants";

export const OutroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const brainScale = spring({
    frame,
    fps,
    config: { damping: 12, stiffness: 80 },
  });

  const titleOpacity = interpolate(frame, [10, 35], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const subtitleOpacity = interpolate(frame, [35, 55], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const taglineOpacity = interpolate(frame, [55, 75], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <div
        style={{
          fontSize: 80,
          transform: `scale(${brainScale})`,
          marginBottom: 30,
        }}
      >
        🧠
      </div>

      <div style={{ opacity: titleOpacity, textAlign: "center" }}>
        <h2
          style={{
            fontFamily: "SF Pro Display, -apple-system, sans-serif",
            fontSize: 60,
            fontWeight: 700,
            color: COLORS.textWhite,
            margin: 0,
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
        </h2>
      </div>

      <div style={{ opacity: subtitleOpacity, marginTop: 20 }}>
        <p
          style={{
            fontFamily: "SF Pro Display, -apple-system, sans-serif",
            fontSize: 30,
            color: COLORS.textGray,
            margin: 0,
            textAlign: "center",
          }}
        >
          Capture everything. Organize nothing.
        </p>
      </div>

      <div style={{ opacity: taglineOpacity, marginTop: 40 }}>
        <div
          style={{
            fontFamily: "SF Mono, monospace",
            fontSize: 18,
            color: COLORS.textDim,
          }}
        >
          Built by Will Macdonald
        </div>
      </div>
    </AbsoluteFill>
  );
};

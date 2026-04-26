import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  interpolate,
  spring,
  useVideoConfig,
} from "remotion";
import { COLORS } from "./constants";

const FeatureRow: React.FC<{
  icon: string;
  title: string;
  subtitle: string;
  color: string;
  delay: number;
  frame: number;
  fps: number;
}> = ({ icon, title, subtitle, color, delay, frame, fps }) => {
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
        transform: `translateX(${interpolate(entrance, [0, 1], [60, 0])}px)`,
        display: "flex",
        alignItems: "center",
        gap: 24,
        padding: "20px 28px",
        borderRadius: 16,
        background: `${COLORS.bgMedium}90`,
        border: `1px solid ${color}20`,
        marginBottom: 16,
      }}
    >
      <div
        style={{
          width: 56,
          height: 56,
          borderRadius: 14,
          background: `${color}20`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 28,
          flexShrink: 0,
        }}
      >
        {icon}
      </div>
      <div>
        <div
          style={{
            fontFamily: "SF Pro Display, -apple-system, sans-serif",
            fontSize: 26,
            fontWeight: 600,
            color: COLORS.textWhite,
          }}
        >
          {title}
        </div>
        <div
          style={{
            fontFamily: "SF Pro Display, -apple-system, sans-serif",
            fontSize: 18,
            color: COLORS.textGray,
            marginTop: 4,
          }}
        >
          {subtitle}
        </div>
      </div>
    </div>
  );
};

export const FutureScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleOpacity = interpolate(frame, [0, 25], [0, 1], {
    extrapolateRight: "clamp",
  });

  // 1290 frame duration
  const exitOpacity = interpolate(frame, [1250, 1290], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ padding: "80px 120px", opacity: exitOpacity }}>
      {/* Section label */}
      <div style={{ opacity: titleOpacity, marginBottom: 40 }}>
        <span
          style={{
            fontFamily: "SF Mono, monospace",
            fontSize: 18,
            color: COLORS.accentCyan,
            textTransform: "uppercase",
            letterSpacing: 4,
          }}
        >
          04 — What's Next
        </span>
        <h2
          style={{
            fontFamily: "SF Pro Display, -apple-system, sans-serif",
            fontSize: 56,
            fontWeight: 700,
            color: COLORS.textWhite,
            margin: "12px 0 0 0",
          }}
        >
          The{" "}
          <span
            style={{
              background: `linear-gradient(135deg, ${COLORS.accentOrange}, ${COLORS.accentPink})`,
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            Roadmap
          </span>
        </h2>
      </div>

      <div style={{ display: "flex", gap: 60 }}>
        {/* Left column: Near-term */}
        <div style={{ flex: 1 }}>
          <div
            style={{
              fontFamily: "SF Mono, monospace",
              fontSize: 14,
              color: COLORS.accentGreen,
              textTransform: "uppercase",
              letterSpacing: 3,
              marginBottom: 20,
              opacity: interpolate(frame, [30, 50], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              }),
            }}
          >
            Coming Soon
          </div>
          <FeatureRow
            icon="🔗"
            title="Recipe URL Extraction"
            subtitle="Paste a recipe link, get a shopping list"
            color={COLORS.accentPink}
            delay={70}
            frame={frame}
            fps={fps}
          />
          <FeatureRow
            icon="🎙"
            title="On-Device Transcription"
            subtitle="iOS SpeechAnalyzer — lower latency, zero cost"
            color={COLORS.accentCyan}
            delay={180}
            frame={frame}
            fps={fps}
          />
          <FeatureRow
            icon="🔔"
            title="Push Notifications"
            subtitle="Know when agents finish processing"
            color={COLORS.accentBlue}
            delay={290}
            frame={frame}
            fps={fps}
          />
        </div>

        {/* Right column: Vision */}
        <div style={{ flex: 1 }}>
          <div
            style={{
              fontFamily: "SF Mono, monospace",
              fontSize: 14,
              color: COLORS.accentPurple,
              textTransform: "uppercase",
              letterSpacing: 3,
              marginBottom: 20,
              opacity: interpolate(frame, [500, 530], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              }),
            }}
          >
            Long-Term Vision
          </div>
          <FeatureRow
            icon="📋"
            title="Projects Agent"
            subtitle="Track actions, deadlines, and progress"
            color={COLORS.accentGreen}
            delay={550}
            frame={frame}
            fps={fps}
          />
          <FeatureRow
            icon="💡"
            title="Ideas Agent"
            subtitle="Weekly check-ins to keep ideas alive"
            color={COLORS.accentOrange}
            delay={680}
            frame={frame}
            fps={fps}
          />
          <FeatureRow
            icon="👥"
            title="People Agent"
            subtitle="Relationship tracking and interaction nudges"
            color={COLORS.accentBlue}
            delay={810}
            frame={frame}
            fps={fps}
          />
          <FeatureRow
            icon="📰"
            title="Daily & Weekly Digests"
            subtitle="Morning brief + Sunday review"
            color={COLORS.accentPurple}
            delay={940}
            frame={frame}
            fps={fps}
          />
        </div>
      </div>
    </AbsoluteFill>
  );
};

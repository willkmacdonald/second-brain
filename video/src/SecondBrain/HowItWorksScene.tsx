import React from "react";
import {
  AbsoluteFill,
  useCurrentFrame,
  interpolate,
  spring,
  useVideoConfig,
} from "remotion";
import { COLORS } from "./constants";

const FlowStep: React.FC<{
  step: number;
  icon: string;
  title: string;
  detail: string;
  color: string;
  delay: number;
  frame: number;
  fps: number;
}> = ({ step, icon, title, detail, color, delay, frame, fps }) => {
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
        transform: `translateY(${interpolate(entrance, [0, 1], [40, 0])}px)`,
        display: "flex",
        alignItems: "flex-start",
        gap: 24,
        marginBottom: 6,
      }}
    >
      {/* Step number + line */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          flexShrink: 0,
        }}
      >
        <div
          style={{
            width: 52,
            height: 52,
            borderRadius: 16,
            background: `${color}25`,
            border: `2px solid ${color}60`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 26,
          }}
        >
          {icon}
        </div>
        {step < 5 && (
          <div
            style={{
              width: 2,
              height: 32,
              background: `${COLORS.textDim}30`,
              marginTop: 6,
            }}
          />
        )}
      </div>

      {/* Content */}
      <div style={{ paddingTop: 4 }}>
        <div
          style={{
            fontFamily: "SF Mono, monospace",
            fontSize: 13,
            color: COLORS.textDim,
            marginBottom: 4,
          }}
        >
          STEP {step}
        </div>
        <div
          style={{
            fontFamily: "SF Pro Display, -apple-system, sans-serif",
            fontSize: 28,
            fontWeight: 600,
            color: COLORS.textWhite,
          }}
        >
          {title}
        </div>
        <div
          style={{
            fontFamily: "SF Pro Display, -apple-system, sans-serif",
            fontSize: 20,
            color: COLORS.textGray,
            marginTop: 4,
          }}
        >
          {detail}
        </div>
      </div>
    </div>
  );
};

const TechBadge: React.FC<{
  label: string;
  delay: number;
  frame: number;
  fps: number;
}> = ({ label, delay, frame, fps }) => {
  const entrance = spring({
    frame: frame - delay,
    fps,
    config: { damping: 15, stiffness: 120 },
  });

  return (
    <div
      style={{
        opacity: interpolate(frame - delay, [0, 10], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        }),
        transform: `scale(${entrance})`,
        fontFamily: "SF Mono, monospace",
        fontSize: 15,
        color: COLORS.textGray,
        background: `${COLORS.bgLight}80`,
        border: `1px solid ${COLORS.textDim}30`,
        borderRadius: 8,
        padding: "8px 16px",
      }}
    >
      {label}
    </div>
  );
};

export const HowItWorksScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleOpacity = interpolate(frame, [0, 25], [0, 1], {
    extrapolateRight: "clamp",
  });

  // 720 frame duration
  const exitOpacity = interpolate(frame, [680, 720], [1, 0], {
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
          03 — How It Works Today
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
          <span style={{ color: COLORS.accentGreen }}>Capture Flow</span>
        </h2>
      </div>

      <div style={{ display: "flex", gap: 80 }}>
        {/* Left: Flow steps */}
        <div style={{ flex: 1.2 }}>
          <FlowStep
            step={1}
            icon="🎙"
            title="Capture"
            detail="Voice note or text — one tap from your phone"
            color={COLORS.accentBlue}
            delay={40}
            frame={frame}
            fps={fps}
          />
          <FlowStep
            step={2}
            icon="🔊"
            title="Transcribe"
            detail="GPT-4o-transcribe converts voice to text"
            color={COLORS.accentPurple}
            delay={110}
            frame={frame}
            fps={fps}
          />
          <FlowStep
            step={3}
            icon="🏷"
            title="Classify"
            detail="Classifier Agent routes to the right bucket"
            color={COLORS.accentCyan}
            delay={180}
            frame={frame}
            fps={fps}
          />
          <FlowStep
            step={4}
            icon="🛒"
            title="Enrich"
            detail="Admin Agent extracts shopping items by store"
            color={COLORS.accentPink}
            delay={250}
            frame={frame}
            fps={fps}
          />
          <FlowStep
            step={5}
            icon="📱"
            title="Review"
            detail="Inbox & Status screen — swipe to manage"
            color={COLORS.accentGreen}
            delay={320}
            frame={frame}
            fps={fps}
          />
        </div>

        {/* Right: Tech stack */}
        <div
          style={{
            flex: 0.8,
            display: "flex",
            flexDirection: "column",
            justifyContent: "center",
          }}
        >
          <div
            style={{
              fontFamily: "SF Pro Display, -apple-system, sans-serif",
              fontSize: 22,
              fontWeight: 600,
              color: COLORS.textDim,
              marginBottom: 24,
              textTransform: "uppercase",
              letterSpacing: 2,
            }}
          >
            Tech Stack
          </div>
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 12,
            }}
          >
            <TechBadge label="FastAPI" delay={380} frame={frame} fps={fps} />
            <TechBadge label="Azure AI Foundry" delay={400} frame={frame} fps={fps} />
            <TechBadge label="Cosmos DB" delay={420} frame={frame} fps={fps} />
            <TechBadge label="GPT-4o" delay={440} frame={frame} fps={fps} />
            <TechBadge label="Expo / React Native" delay={460} frame={frame} fps={fps} />
            <TechBadge label="SSE Streaming" delay={480} frame={frame} fps={fps} />
            <TechBadge label="Container Apps" delay={500} frame={frame} fps={fps} />
            <TechBadge label="GitHub Actions" delay={520} frame={frame} fps={fps} />
            <TechBadge label="App Insights" delay={540} frame={frame} fps={fps} />
          </div>

          {/* Stats */}
          <div
            style={{
              marginTop: 40,
              opacity: interpolate(frame, [560, 590], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              }),
            }}
          >
            <div
              style={{
                display: "flex",
                gap: 40,
              }}
            >
              <div>
                <div
                  style={{
                    fontFamily: "SF Pro Display, -apple-system, sans-serif",
                    fontSize: 42,
                    fontWeight: 700,
                    color: COLORS.accentBlue,
                  }}
                >
                  ~2.8k
                </div>
                <div
                  style={{
                    fontFamily: "SF Pro Display, -apple-system, sans-serif",
                    fontSize: 16,
                    color: COLORS.textDim,
                  }}
                >
                  LOC Python
                </div>
              </div>
              <div>
                <div
                  style={{
                    fontFamily: "SF Pro Display, -apple-system, sans-serif",
                    fontSize: 42,
                    fontWeight: 700,
                    color: COLORS.accentPurple,
                  }}
                >
                  ~19.8k
                </div>
                <div
                  style={{
                    fontFamily: "SF Pro Display, -apple-system, sans-serif",
                    fontSize: 16,
                    color: COLORS.textDim,
                  }}
                >
                  LOC TypeScript
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

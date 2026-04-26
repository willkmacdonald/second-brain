import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { COLORS } from "./constants";

const ContractRow: React.FC<{
  label: string;
  value: string;
  color: string;
  frame: number;
  delay: number;
}> = ({ label, value, color, frame, delay }) => {
  const opacity = interpolate(frame - delay, [0, 18], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const x = interpolate(frame - delay, [0, 18], [20, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        opacity,
        transform: `translateX(${x}px)`,
        display: "grid",
        gridTemplateColumns: "220px 1fr",
        gap: 18,
        padding: "18px 20px",
        borderRadius: 14,
        background: "rgba(15, 23, 42, 0.72)",
        border: `1px solid ${color}38`,
        fontFamily: "Arial, sans-serif",
      }}
    >
      <div style={{ color, fontSize: 17, fontWeight: 900 }}>{label}</div>
      <div style={{ color: COLORS.textGray, fontSize: 19, lineHeight: 1.35 }}>{value}</div>
    </div>
  );
};

export const InstructionsScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const panelScale = spring({
    frame,
    fps,
    config: { damping: 17, stiffness: 78 },
  });
  const exitOpacity = interpolate(frame, [735, 779], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ padding: "70px 116px", opacity: exitOpacity }}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "0.78fr 1.22fr",
          gap: 48,
          alignItems: "center",
          height: "100%",
        }}
      >
        <div>
          <div
            style={{
              fontFamily: "Arial, sans-serif",
              color: COLORS.accentCyan,
              fontSize: 15,
              textTransform: "uppercase",
              letterSpacing: 4,
              fontWeight: 900,
            }}
          >
            Managed Instructions
          </div>
          <div
            style={{
              fontFamily: "Arial, sans-serif",
              color: COLORS.textWhite,
              fontSize: 68,
              fontWeight: 900,
              lineHeight: 0.98,
              marginTop: 12,
            }}
          >
            Every agent has one job.
          </div>
          <div
            style={{
              fontFamily: "Arial, sans-serif",
              color: COLORS.textGray,
              fontSize: 25,
              lineHeight: 1.35,
              marginTop: 26,
              maxWidth: 650,
            }}
          >
            Foundry-managed prompts define the agent contract: what the agent
            does, what it must not do, and which tools it can call.
          </div>
        </div>

        <div
          style={{
            transform: `scale(${interpolate(panelScale, [0, 1], [0.96, 1])})`,
            padding: 30,
            borderRadius: 26,
            background: "rgba(5, 9, 18, 0.72)",
            border: `1px solid ${COLORS.accentCyan}28`,
            boxShadow: `0 28px 80px rgba(0,0,0,0.34), 0 0 60px ${COLORS.accentCyan}10`,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 22,
            }}
          >
            <div>
              <div
                style={{
                  fontFamily: "Arial, sans-serif",
                  color: COLORS.textGray,
                  fontSize: 15,
                  fontWeight: 900,
                  textTransform: "uppercase",
                  letterSpacing: 2.4,
                }}
              >
                Agent
              </div>
              <div
                style={{
                  fontFamily: "Arial, sans-serif",
                  color: COLORS.textWhite,
                  fontSize: 42,
                  fontWeight: 900,
                  marginTop: 6,
                }}
              >
                Classifier
              </div>
            </div>
            <div
              style={{
                padding: "13px 17px",
                borderRadius: 14,
                background: "rgba(59, 130, 246, 0.12)",
                border: `1px solid ${COLORS.accentBlue}40`,
                color: COLORS.accentBlue,
                fontFamily: "SF Mono, Menlo, monospace",
                fontSize: 17,
                fontWeight: 900,
              }}
            >
              gpt-4o
            </div>
          </div>

          <div
            style={{
              padding: "22px 24px",
              borderRadius: 18,
              background: "rgba(148, 163, 184, 0.08)",
              border: `1px solid ${COLORS.textDim}22`,
              marginBottom: 20,
            }}
          >
            <div
              style={{
                fontFamily: "SF Mono, Menlo, monospace",
                color: COLORS.textGray,
                fontSize: 19,
                lineHeight: 1.52,
              }}
            >
              Classify captured input into the correct destination. Use only
              approved filing tools. Do not compose digests. Do not create next
              steps. Return control to the orchestrator when finished.
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 13 }}>
            <ContractRow
              label="Allowed buckets"
              value="Admin, Projects, People, Ideas"
              color={COLORS.accentBlue}
              frame={frame}
              delay={72}
            />
            <ContractRow
              label="Tool contract"
              value="file_to_bucket(bucket, confidence, trace_context)"
              color={COLORS.accentCyan}
              frame={frame}
              delay={112}
            />
            <ContractRow
              label="Boundary"
              value="The classifier does not route stores. The Admin Agent does not classify buckets. The Investigation Agent does not file captures."
              color={COLORS.accentOrange}
              frame={frame}
              delay={152}
            />
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

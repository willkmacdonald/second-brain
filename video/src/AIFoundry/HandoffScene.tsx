import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import {
  COLORS,
  SECOND_BRAIN_CHAIN,
  SECOND_BRAIN_INDEPENDENT,
} from "./constants";

const NODE_SIZE = 108;
const START_X = 148;
const NODE_GAP = 190;
const FLOW_Y = 245;

const VoiceNote: React.FC<{ frame: number }> = ({ frame }) => {
  const endX = START_X + (SECOND_BRAIN_CHAIN.length - 1) * (NODE_SIZE + NODE_GAP) + NODE_SIZE + 76;
  const x = interpolate(frame, [80, 440], [START_X - 92, endX], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const opacity = interpolate(frame, [45, 80, 470, 540], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: FLOW_Y,
        transform: "translate(-50%, -50%)",
        opacity,
        width: 46,
        height: 46,
        borderRadius: 16,
        background: "rgba(6, 182, 212, 0.16)",
        border: `1px solid ${COLORS.accentCyan}66`,
        boxShadow: `0 0 24px ${COLORS.accentCyan}44`,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          width: 10,
          height: 24,
          borderRadius: 8,
          border: `2px solid ${COLORS.accentCyan}`,
        }}
      />
    </div>
  );
};

const FlowNode: React.FC<{
  name: string;
  role: string;
  color: string;
  index: number;
  frame: number;
}> = ({ name, role, color, index, frame }) => {
  const activeIndex = Math.min(
    SECOND_BRAIN_CHAIN.length - 1,
    Math.floor(
      interpolate(frame, [92, 430], [0, SECOND_BRAIN_CHAIN.length], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    )
  );
  const isActive = activeIndex === index;
  const isPast = index < activeIndex;
  const opacity = interpolate(frame - index * 48, [0, 24], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        position: "absolute",
        left: START_X + index * (NODE_SIZE + NODE_GAP),
        top: FLOW_Y,
        width: NODE_SIZE,
        transform: "translateY(-50%)",
        opacity,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
      }}
    >
      <div
        style={{
          width: NODE_SIZE,
          height: NODE_SIZE,
          borderRadius: 26,
          background: isActive ? `${color}22` : "rgba(30, 41, 59, 0.74)",
          border: `2px solid ${color}${isActive ? "aa" : isPast ? "66" : "38"}`,
          boxShadow: isActive ? `0 0 34px ${color}55` : "none",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          textAlign: "center",
          color: isActive ? color : COLORS.textGray,
          fontFamily: "Arial, sans-serif",
          fontSize: 15,
          fontWeight: 900,
          lineHeight: 1.08,
          padding: 12,
        }}
      >
        {name}
      </div>
      <div
        style={{
          marginTop: 12,
          color: COLORS.textDim,
          fontFamily: "Arial, sans-serif",
          fontSize: 14,
          textAlign: "center",
          lineHeight: 1.22,
          width: 170,
        }}
      >
        {role}
      </div>
    </div>
  );
};

const RouteChip: React.FC<{
  label: string;
  detail: string;
  delay: number;
  frame: number;
}> = ({ label, detail, delay, frame }) => {
  const opacity = interpolate(frame - delay, [0, 20], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <div
      style={{
        opacity,
        padding: "13px 15px",
        borderRadius: 14,
        background: "rgba(16, 185, 129, 0.10)",
        border: `1px solid ${COLORS.accentGreen}38`,
        fontFamily: "Arial, sans-serif",
      }}
    >
      <div style={{ color: COLORS.textWhite, fontSize: 17, fontWeight: 900 }}>{label}</div>
      <div style={{ color: COLORS.textDim, fontSize: 13, marginTop: 4 }}>{detail}</div>
    </div>
  );
};

const ScheduleCard: React.FC<{
  name: string;
  role: string;
  delay: number;
  frame: number;
}> = ({ name, role, delay, frame }) => {
  const opacity = interpolate(frame - delay, [0, 24], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const pulse = interpolate((frame + delay) % 88, [0, 44, 88], [0.25, 1, 0.25], {
    extrapolateRight: "clamp",
  });
  return (
    <div
      style={{
        opacity,
        flex: 1,
        minHeight: 92,
        padding: "18px 20px",
        borderRadius: 18,
        background: "rgba(210, 153, 34, 0.08)",
        border: "1px solid rgba(210, 153, 34, 0.34)",
        boxShadow: `0 0 ${12 + pulse * 16}px rgba(210, 153, 34, 0.16)`,
        fontFamily: "Arial, sans-serif",
      }}
    >
      <div style={{ color: COLORS.textWhite, fontSize: 20, fontWeight: 900 }}>{name}</div>
      <div style={{ color: COLORS.textDim, fontSize: 14, marginTop: 6 }}>{role}</div>
      <div style={{ color: COLORS.accentOrange, fontSize: 12, fontWeight: 900, marginTop: 9 }}>
        independent schedule
      </div>
    </div>
  );
};

export const HandoffScene: React.FC = () => {
  const frame = useCurrentFrame();
  const exitOpacity = interpolate(frame, [610, 650], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const activeIndex = Math.min(
    SECOND_BRAIN_CHAIN.length - 1,
    Math.floor(
      interpolate(frame, [92, 430], [0, SECOND_BRAIN_CHAIN.length], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    )
  );

  return (
    <AbsoluteFill style={{ padding: "58px 82px", opacity: exitOpacity }}>
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
        Handoff Pattern
      </div>
      <div
        style={{
          fontFamily: "Arial, sans-serif",
          color: COLORS.textWhite,
          fontSize: 58,
          lineHeight: 1.02,
          fontWeight: 900,
          marginTop: 10,
          maxWidth: 1280,
        }}
      >
        The orchestrator transfers control, then hands Admin work forward.
      </div>

      <div
        style={{
          position: "absolute",
          left: 82,
          top: 238,
          width: 1030,
          height: 490,
          borderRadius: 30,
          background: "rgba(5, 9, 18, 0.62)",
          border: `1px solid ${COLORS.accentCyan}24`,
          boxShadow: "inset 0 1px 0 rgba(255,255,255,0.04)",
        }}
      >
        {SECOND_BRAIN_CHAIN.map((node, index) => (
          <FlowNode
            key={node.name}
            name={node.name}
            role={node.role}
            color={node.color}
            index={index}
            frame={frame}
          />
        ))}

        {SECOND_BRAIN_CHAIN.slice(0, -1).map((_, index) => {
          const x1 = START_X + index * (NODE_SIZE + NODE_GAP) + NODE_SIZE;
          const x2 = START_X + (index + 1) * (NODE_SIZE + NODE_GAP);
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
                top: FLOW_Y,
                width: x2 - x1,
                height: 3,
                background: isActive ? `${COLORS.accentCyan}70` : `${COLORS.textDim}28`,
              }}
            >
              {isPulsing && (
                <div
                  style={{
                    position: "absolute",
                    left: `${pulse * 100}%`,
                    top: -5,
                    width: 13,
                    height: 13,
                    borderRadius: "50%",
                    background: COLORS.accentCyan,
                    boxShadow: `0 0 18px ${COLORS.accentCyan}`,
                    transform: "translateX(-50%)",
                  }}
                />
              )}
            </div>
          );
        })}

        <VoiceNote frame={frame} />

        <div
          style={{
            position: "absolute",
            right: 44,
            top: 42,
            opacity: interpolate(frame, [430, 500], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            color: COLORS.accentGreen,
            fontFamily: "Arial, sans-serif",
            fontSize: 22,
            fontWeight: 900,
            padding: "13px 18px",
            borderRadius: 16,
            background: `${COLORS.accentGreen}12`,
            border: `1px solid ${COLORS.accentGreen}34`,
            boxShadow: `0 0 26px ${COLORS.accentGreen}18`,
          }}
        >
          Filed → Admin
        </div>
      </div>

      <div
        style={{
          position: "absolute",
          right: 82,
          top: 238,
          width: 640,
          height: 490,
          display: "grid",
          gridTemplateRows: "1fr 1fr",
          gap: 18,
        }}
      >
        <div
          style={{
            padding: 22,
            borderRadius: 24,
            background: "rgba(5, 9, 18, 0.62)",
            border: `1px solid ${COLORS.accentGreen}24`,
          }}
        >
          <div
            style={{
              fontFamily: "Arial, sans-serif",
              color: COLORS.accentGreen,
              fontSize: 13,
              fontWeight: 900,
              textTransform: "uppercase",
              letterSpacing: 2.5,
              marginBottom: 13,
            }}
          >
            Admin Agent routes
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <RouteChip label="Jewel-Osco" detail="groceries" delay={348} frame={frame} />
            <RouteChip label="CVS" detail="pharmacy" delay={374} frame={frame} />
            <RouteChip label="Chewy.com" detail="auto-order" delay={400} frame={frame} />
            <RouteChip label="Tasks" detail="follow-up" delay={426} frame={frame} />
          </div>
        </div>

        <div
          style={{
            padding: 22,
            borderRadius: 24,
            background: "rgba(5, 9, 18, 0.62)",
            border: `1px solid ${COLORS.accentOrange}24`,
          }}
        >
          <div
            style={{
              fontFamily: "Arial, sans-serif",
              color: COLORS.accentOrange,
              fontSize: 13,
              fontWeight: 900,
              textTransform: "uppercase",
              letterSpacing: 2.5,
              marginBottom: 14,
            }}
          >
            Scheduled agents
          </div>
          <div style={{ display: "flex", gap: 12 }}>
            {SECOND_BRAIN_INDEPENDENT.map((node, index) => (
              <ScheduleCard
                key={node.name}
                name={node.name}
                role={node.role}
                delay={450 + index * 42}
                frame={frame}
              />
            ))}
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

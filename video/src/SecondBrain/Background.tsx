import React from "react";
import { AbsoluteFill, useCurrentFrame, interpolate } from "remotion";
import { COLORS, TOTAL_DURATION } from "./constants";

export const Background: React.FC = () => {
  const frame = useCurrentFrame();

  // Slowly shifting gradient angle
  const angle = interpolate(frame, [0, TOTAL_DURATION], [135, 225]);

  // Floating orbs
  const orb1X = interpolate(frame, [0, TOTAL_DURATION], [10, 60]);
  const orb1Y = interpolate(frame, [0, TOTAL_DURATION], [20, 70]);
  const orb2X = interpolate(frame, [0, TOTAL_DURATION], [80, 30]);
  const orb2Y = interpolate(frame, [0, TOTAL_DURATION], [70, 20]);

  return (
    <AbsoluteFill
      style={{
        background: `linear-gradient(${angle}deg, ${COLORS.bgDark} 0%, #0c1220 50%, ${COLORS.bgDark} 100%)`,
      }}
    >
      {/* Floating gradient orbs */}
      <div
        style={{
          position: "absolute",
          width: 600,
          height: 600,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${COLORS.accentBlue}15 0%, transparent 70%)`,
          left: `${orb1X}%`,
          top: `${orb1Y}%`,
          transform: "translate(-50%, -50%)",
          filter: "blur(40px)",
        }}
      />
      <div
        style={{
          position: "absolute",
          width: 500,
          height: 500,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${COLORS.accentPurple}12 0%, transparent 70%)`,
          left: `${orb2X}%`,
          top: `${orb2Y}%`,
          transform: "translate(-50%, -50%)",
          filter: "blur(40px)",
        }}
      />

      {/* Subtle grid pattern */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage: `
            linear-gradient(${COLORS.textDim}08 1px, transparent 1px),
            linear-gradient(90deg, ${COLORS.textDim}08 1px, transparent 1px)
          `,
          backgroundSize: "60px 60px",
        }}
      />
    </AbsoluteFill>
  );
};

import React from "react";
import { AbsoluteFill, useCurrentFrame, interpolate } from "remotion";
import { COLORS, TOTAL_DURATION } from "./constants";

export const Background: React.FC = () => {
  const frame = useCurrentFrame();

  const scanlineY = interpolate(frame, [0, TOTAL_DURATION], [-10, 110]);
  const gridOffset = interpolate(frame, [0, TOTAL_DURATION], [0, 60]);

  return (
    <AbsoluteFill
      style={{
        background: `
          radial-gradient(ellipse at 50% 18%, rgba(20, 184, 166, 0.11) 0%, rgba(20, 184, 166, 0.02) 34%, transparent 64%),
          linear-gradient(180deg, #05070d 0%, #0a1020 48%, #05070d 100%)
        `,
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage: `
            linear-gradient(${COLORS.textDim}0a 1px, transparent 1px),
            linear-gradient(90deg, ${COLORS.textDim}0a 1px, transparent 1px)
          `,
          backgroundSize: "60px 60px",
          backgroundPosition: `${gridOffset}px ${gridOffset}px`,
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "linear-gradient(90deg, rgba(255,255,255,0.08) 0%, transparent 18%, transparent 82%, rgba(255,255,255,0.08) 100%)",
          opacity: 0.18,
        }}
      />
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: `${scanlineY}%`,
          height: 180,
          background: `linear-gradient(180deg, transparent 0%, ${COLORS.accentCyan}0d 50%, transparent 100%)`,
          transform: "translateY(-50%)",
        }}
      />
    </AbsoluteFill>
  );
};

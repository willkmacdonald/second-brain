import React from "react";
import { Audio, Sequence, staticFile } from "remotion";
import { Background } from "./Background";
import { AgentPanelScene } from "./AgentPanelScene";
import { InstructionsScene } from "./InstructionsScene";
import { HandoffScene } from "./HandoffScene";
import { SplitScreenScene } from "./SplitScreenScene";
import { SCENES } from "./constants";

export const AIFoundryVideo: React.FC = () => {
  return (
    <>
      <Background />
      <Audio src={staticFile("breakout-ai-foundry.mp3")} />

      <Sequence
        from={SCENES.agentPanel.start}
        durationInFrames={SCENES.agentPanel.duration}
      >
        <AgentPanelScene />
      </Sequence>

      <Sequence
        from={SCENES.instructions.start}
        durationInFrames={SCENES.instructions.duration}
      >
        <InstructionsScene />
      </Sequence>

      <Sequence
        from={SCENES.handoff.start}
        durationInFrames={SCENES.handoff.duration}
      >
        <HandoffScene />
      </Sequence>

      <Sequence
        from={SCENES.splitScreen.start}
        durationInFrames={SCENES.splitScreen.duration}
      >
        <SplitScreenScene />
      </Sequence>
    </>
  );
};

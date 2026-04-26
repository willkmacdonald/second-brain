import React from "react";
import { Audio, Sequence, staticFile } from "remotion";
import { Background } from "./Background";
import { IntroScene } from "./IntroScene";
import { WhatItIsScene } from "./WhatItIsScene";
import { VisionScene } from "./VisionScene";
import { HowItWorksScene } from "./HowItWorksScene";
import { FutureScene } from "./FutureScene";
import { OutroScene } from "./OutroScene";
import { SECTIONS } from "./constants";

export const SecondBrainOverview: React.FC = () => {
  return (
    <>
      <Audio src={staticFile("voiceover.mp3")} />
      <Background />

      <Sequence from={SECTIONS.intro.start} durationInFrames={SECTIONS.intro.duration}>
        <IntroScene />
      </Sequence>

      <Sequence from={SECTIONS.whatItIs.start} durationInFrames={SECTIONS.whatItIs.duration}>
        <WhatItIsScene />
      </Sequence>

      <Sequence from={SECTIONS.vision.start} durationInFrames={SECTIONS.vision.duration}>
        <VisionScene />
      </Sequence>

      <Sequence from={SECTIONS.howItWorks.start} durationInFrames={SECTIONS.howItWorks.duration}>
        <HowItWorksScene />
      </Sequence>

      <Sequence from={SECTIONS.future.start} durationInFrames={SECTIONS.future.duration}>
        <FutureScene />
      </Sequence>

      <Sequence from={SECTIONS.outro.start} durationInFrames={SECTIONS.outro.duration}>
        <OutroScene />
      </Sequence>
    </>
  );
};

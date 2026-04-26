import { Composition } from "remotion";
import { SecondBrainOverview } from "./SecondBrain";
import { TOTAL_DURATION, FPS } from "./SecondBrain/constants";
import { SecondBrainShoppingFilm } from "./ShoppingFilm";
import {
  SHOPPING_FILM_DURATION,
  SHOPPING_FILM_FPS,
  SHOPPING_FILM_HEIGHT,
  SHOPPING_FILM_WIDTH,
} from "./ShoppingFilm/constants";
import { AIFoundryVideo } from "./AIFoundry";
import {
  TOTAL_DURATION as AI_FOUNDRY_DURATION,
  FPS as AI_FOUNDRY_FPS,
} from "./AIFoundry/constants";
import { BreakoutObservabilityVideo } from "./Observability";
import {
  OBS_FPS,
  OBS_TOTAL_DURATION,
} from "./Observability/constants";
import { BreakoutEvalsVideo } from "./Evals";
import {
  EVALS_FPS,
  EVALS_TOTAL_DURATION,
} from "./Evals/constants";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="SecondBrainOverview"
        component={SecondBrainOverview}
        durationInFrames={TOTAL_DURATION}
        fps={FPS}
        width={1920}
        height={1080}
      />
      <Composition
        id="SecondBrainShoppingFilm"
        component={SecondBrainShoppingFilm}
        durationInFrames={SHOPPING_FILM_DURATION}
        fps={SHOPPING_FILM_FPS}
        width={SHOPPING_FILM_WIDTH}
        height={SHOPPING_FILM_HEIGHT}
      />
      <Composition
        id="BreakoutAIFoundry"
        component={AIFoundryVideo}
        durationInFrames={AI_FOUNDRY_DURATION}
        fps={AI_FOUNDRY_FPS}
        width={1920}
        height={1080}
      />
      <Composition
        id="BreakoutObservability"
        component={BreakoutObservabilityVideo}
        durationInFrames={OBS_TOTAL_DURATION}
        fps={OBS_FPS}
        width={1920}
        height={1080}
      />
      <Composition
        id="BreakoutEvals"
        component={BreakoutEvalsVideo}
        durationInFrames={EVALS_TOTAL_DURATION}
        fps={EVALS_FPS}
        width={1920}
        height={1080}
      />
    </>
  );
};

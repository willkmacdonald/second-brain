export type StoryMoment = {
  id: string;
  label: string;
  voiceover: string;
};

export const STORYBOARD: StoryMoment[] = [
  {
    id: "opening",
    label: "Premium product opening",
    voiceover:
      "One voice capture becomes a coordinated shopping plan, online order, and end to end evidence trail.",
  },
  {
    id: "phone-capture",
    label: "iPhone capture with Listening and Classifying states",
    voiceover:
      "The phone stays simple: tap to record, watch Listening become Classifying, see green light / red light health, and let the system do the work.",
  },
  {
    id: "chewy-commerce",
    label: "Chewy automatic order placement",
    voiceover:
      "Onions, garlic, cilantro, milk, steak, and Tylenol become local errands. Cat food routes to Chewy for automatic order placement.",
  },
  {
    id: "front-to-back-observability",
    label: "Web trace from front to back",
    voiceover:
      "The web experience traces the transaction from front to back across mobile capture, classifier, admin agent, Cosmos, and commerce.",
  },
  {
    id: "classifier",
    label: "Classifier and admin instructions and rule checks",
    voiceover:
      "The classifier agent applies Foundry-managed instructions, then the admin agent splits destinations, routes errands, and places the Chewy order with trace context.",
  },
  {
    id: "observability",
    label: "Observability details",
    voiceover:
      "Segment detail comes from mobile capture IDs, Foundry agent runs, admin routing decisions, Cosmos request IDs, App Insights queries, and commerce confirmations.",
  },
  {
    id: "evals",
    label: "Eval request and self improvement",
    voiceover:
      "The user can request an eval from the phone, check back later, and see the self improvement loop without reading backend logs.",
  },
];

export const VOICE_CAPTURE_TEXT =
  "I want to buy onions, garlic, cilantro, steak, milk, Tylenol and cat food.";

export const SHOPPING_RESULTS = [
  { destination: "Jewel-Osco", item: "Onions", mode: "Errand" },
  { destination: "Jewel-Osco", item: "Garlic", mode: "Errand" },
  { destination: "Jewel-Osco", item: "Cilantro", mode: "Errand" },
  { destination: "Agora", item: "Steak", mode: "Errand" },
  { destination: "Jewel-Osco", item: "Milk", mode: "Errand" },
  { destination: "CVS", item: "Tylenol", mode: "Errand" },
  { destination: "Chewy", item: "Cat food", mode: "Automatic order" },
] as const;

export type AGUIEventType =
  | "message"
  | "RUN_STARTED"
  | "TEXT_MESSAGE_START"
  | "TEXT_MESSAGE_CONTENT"
  | "TEXT_MESSAGE_END"
  | "STEP_STARTED"
  | "STEP_FINISHED"
  | "TOOL_CALL_START"
  | "TOOL_CALL_END"
  | "CUSTOM"
  | "RUN_FINISHED"
  | "RUN_ERROR";

export interface StreamingCallbacks {
  onStepStart?: (stepName: string) => void;
  onStepFinish?: (stepName: string) => void;
  onTextDelta?: (delta: string) => void;
  onHITLRequired?: (threadId: string, questionText: string, inboxItemId?: string) => void;
  onMisunderstood?: (threadId: string, questionText: string, inboxItemId: string) => void;
  onUnresolved?: (inboxItemId: string) => void;
  onComplete: (result: string) => void;
  onError: (error: string) => void;
}

export interface SendCaptureOptions {
  message: string;
  apiKey: string;
  callbacks: StreamingCallbacks;
}

export interface SendClarificationOptions {
  threadId: string;
  bucket: string;
  apiKey: string;
  callbacks: StreamingCallbacks;
  inboxItemId?: string;
}

export interface SendFollowUpOptions {
  inboxItemId: string;
  followUpText: string;
  followUpRound: number;
  apiKey: string;
  callbacks: StreamingCallbacks;
}

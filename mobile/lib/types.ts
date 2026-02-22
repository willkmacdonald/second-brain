export type AGUIEventType =
  | "RUN_STARTED"
  | "TEXT_MESSAGE_START"
  | "TEXT_MESSAGE_CONTENT"
  | "TEXT_MESSAGE_END"
  | "RUN_FINISHED"
  | "RUN_ERROR";

export interface SendCaptureOptions {
  message: string;
  apiKey: string;
  onComplete: (result: string) => void;
  onError: (error: string) => void;
}

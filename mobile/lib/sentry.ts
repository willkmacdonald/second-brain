import * as Sentry from "@sentry/react-native";
import { isRunningInExpoGo } from "expo";

const navigationIntegration = Sentry.reactNavigationIntegration({
  enableTimeToInitialDisplay: !isRunningInExpoGo(),
});

export function initSentry(): void {
  Sentry.init({
    dsn: process.env.EXPO_PUBLIC_SENTRY_DSN ?? "",
    tracesSampleRate: 1.0, // 100% for single-user app
    enableNativeFramesTracking: !isRunningInExpoGo(),
    integrations: [navigationIntegration],
    sendDefaultPii: false, // No PII -- good hygiene even for single-user
    enabled: !__DEV__, // Disabled in dev to avoid noise
  });
}

export function tagTrace(captureTraceId: string): void {
  Sentry.setTag("capture_trace_id", captureTraceId);
  Sentry.setTag("correlation_kind", "capture");
  Sentry.setTag("correlation_id", captureTraceId);
}

export function clearTraceTags(): void {
  Sentry.setTag("capture_trace_id", undefined as never);
  Sentry.setTag("correlation_kind", undefined as never);
  Sentry.setTag("correlation_id", undefined as never);
}

export { Sentry, navigationIntegration };

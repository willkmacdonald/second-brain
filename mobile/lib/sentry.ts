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

export { Sentry, navigationIntegration };

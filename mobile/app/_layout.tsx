import { useEffect } from "react";
import { Stack, useNavigationContainerRef } from "expo-router";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import * as Sentry from "@sentry/react-native";
import { initSentry, navigationIntegration } from "../lib/sentry";
import { ErrorFallback } from "../components/ErrorFallback";

// Initialize Sentry at module scope -- BEFORE any rendering (Pitfall 3)
initSentry();

function RootLayout() {
  const ref = useNavigationContainerRef();

  useEffect(() => {
    if (ref?.current) {
      navigationIntegration.registerNavigationContainer(ref);
    }
  }, [ref]);

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <Sentry.ErrorBoundary fallback={ErrorFallback}>
        <Stack screenOptions={{ headerShown: false }}>
          <Stack.Screen name="(tabs)" />
          <Stack.Screen
            name="conversation/[threadId]"
            options={{
              headerShown: true,
              headerTitle: "",
              headerStyle: { backgroundColor: "#0f0f23" },
              headerTintColor: "#ffffff",
            }}
          />
        </Stack>
      </Sentry.ErrorBoundary>
    </GestureHandlerRootView>
  );
}

export default Sentry.wrap(RootLayout);

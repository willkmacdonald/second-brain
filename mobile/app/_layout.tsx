import { useEffect } from "react";
import { Stack, useNavigationContainerRef, SplashScreen } from "expo-router";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import * as Sentry from "@sentry/react-native";
import { useFonts } from "expo-font";
import {
  InstrumentSerif_400Regular,
  InstrumentSerif_400Regular_Italic,
} from "@expo-google-fonts/instrument-serif";
import {
  InstrumentSans_400Regular,
  InstrumentSans_500Medium,
  InstrumentSans_600SemiBold,
  InstrumentSans_700Bold,
} from "@expo-google-fonts/instrument-sans";
import { JetBrainsMono_400Regular } from "@expo-google-fonts/jetbrains-mono";
import { initSentry, navigationIntegration } from "../lib/sentry";
import { ErrorFallback } from "../components/ErrorFallback";
import { ApiKeyProvider } from "../contexts/ApiKeyContext";
import { ApiKeyGate } from "../components/ApiKeyGate";

// Initialize Sentry at module scope -- BEFORE any rendering (Pitfall 3)
initSentry();

// Keep splash screen visible until fonts are loaded
SplashScreen.preventAutoHideAsync();

function RootLayout() {
  const ref = useNavigationContainerRef();

  const [fontsLoaded] = useFonts({
    InstrumentSerif_400Regular,
    InstrumentSerif_400Regular_Italic,
    InstrumentSans_400Regular,
    InstrumentSans_500Medium,
    InstrumentSans_600SemiBold,
    InstrumentSans_700Bold,
    JetBrainsMono_400Regular,
  });

  useEffect(() => {
    if (ref?.current) {
      navigationIntegration.registerNavigationContainer(ref);
    }
  }, [ref]);

  useEffect(() => {
    if (fontsLoaded) {
      SplashScreen.hideAsync();
    }
  }, [fontsLoaded]);

  if (!fontsLoaded) return null;

  return (
    <ApiKeyProvider>
      <ApiKeyGate />
      <GestureHandlerRootView style={{ flex: 1 }}>
        <Sentry.ErrorBoundary fallback={ErrorFallback}>
          <Stack screenOptions={{ headerShown: false }}>
            <Stack.Screen name="(tabs)" />
            <Stack.Screen
              name="conversation/[threadId]"
              options={{
                headerShown: true,
                headerTitle: "",
                headerStyle: { backgroundColor: "#0a0a12" },
                headerTintColor: "#f0f0f5",
              }}
            />
            <Stack.Screen
              name="investigate"
              options={{
                headerShown: true,
                headerTitle: "Investigate",
                headerStyle: { backgroundColor: "#0a0a12" },
                headerTintColor: "#f0f0f5",
              }}
            />
            <Stack.Screen
              name="settings"
              options={{
                headerShown: true,
                headerTitle: "Settings",
                headerStyle: { backgroundColor: "#0a0a12" },
                headerTintColor: "#f0f0f5",
              }}
            />
          </Stack>
        </Sentry.ErrorBoundary>
      </GestureHandlerRootView>
    </ApiKeyProvider>
  );
}

export default Sentry.wrap(RootLayout);

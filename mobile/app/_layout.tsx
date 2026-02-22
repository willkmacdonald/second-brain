import { Stack } from "expo-router";

export default function RootLayout() {
  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="(tabs)" />
      <Stack.Screen
        name="capture/text"
        options={{
          headerShown: true,
          headerTitle: "",
          headerStyle: { backgroundColor: "#0f0f23" },
          headerTintColor: "#ffffff",
          presentation: "modal",
        }}
      />
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
  );
}

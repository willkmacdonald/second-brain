import { Stack } from "expo-router";

export default function RootLayout() {
  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="index" />
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
    </Stack>
  );
}

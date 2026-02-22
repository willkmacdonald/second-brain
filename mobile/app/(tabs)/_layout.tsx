import { Tabs } from "expo-router";

export default function TabLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: {
          backgroundColor: "#0f0f23",
          borderTopColor: "#1a1a2e",
        },
        tabBarActiveTintColor: "#4a90d9",
        tabBarInactiveTintColor: "#666",
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Capture",
          tabBarIcon: ({ color }) => (
            // Simple unicode icon -- no icon library needed for MVP
            <TabIcon label={"\u270F"} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="inbox"
        options={{
          title: "Inbox",
          tabBarIcon: ({ color }) => (
            <TabIcon label={"\uD83D\uDCC2"} color={color} />
          ),
          // Badge count for pending clarifications (Plan 04-03 will populate)
          tabBarBadge: undefined,
        }}
      />
    </Tabs>
  );
}

function TabIcon({ label, color }: { label: string; color: string }) {
  const { Text } = require("react-native");
  return <Text style={{ fontSize: 20, color }}>{label}</Text>;
}

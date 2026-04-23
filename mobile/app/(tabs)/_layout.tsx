import { Tabs } from "expo-router";
import { StyleSheet } from "react-native";
import { Mic, Inbox, CheckSquare, Sparkles } from "lucide-react-native";
import { theme } from "../../constants/theme";

export default function TabLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: {
          backgroundColor: "rgba(10,10,18,0.85)",
          borderTopWidth: StyleSheet.hairlineWidth,
          borderTopColor: theme.colors.hairline,
          height: 70,
          paddingTop: 6,
        },
        tabBarActiveTintColor: theme.colors.text,
        tabBarInactiveTintColor: theme.colors.textMuted,
        tabBarLabelStyle: {
          fontFamily: theme.fonts.bodyMedium,
          fontSize: 10.5,
          letterSpacing: -0.1,
        },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Capture",
          tabBarIcon: ({ color, focused }) => (
            <Mic
              size={22}
              color={color}
              strokeWidth={focused ? 1.8 : 1.4}
            />
          ),
        }}
      />
      <Tabs.Screen
        name="inbox"
        options={{
          title: "Inbox",
          tabBarIcon: ({ color, focused }) => (
            <Inbox
              size={22}
              color={color}
              strokeWidth={focused ? 1.8 : 1.4}
            />
          ),
          // Badge count set dynamically via navigation.setOptions in InboxScreen
          tabBarBadge: undefined,
        }}
      />
      <Tabs.Screen
        name="tasks"
        options={{
          title: "Tasks",
          tabBarIcon: ({ color, focused }) => (
            <CheckSquare
              size={22}
              color={color}
              strokeWidth={focused ? 1.8 : 1.4}
            />
          ),
        }}
      />
      <Tabs.Screen
        name="status"
        options={{
          title: "Status",
          tabBarIcon: ({ color, focused }) => (
            <Sparkles
              size={22}
              color={color}
              strokeWidth={focused ? 1.8 : 1.4}
            />
          ),
        }}
      />
    </Tabs>
  );
}

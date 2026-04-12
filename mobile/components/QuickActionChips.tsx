import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

interface QuickActionChipsProps {
  onSelect: (query: string) => void;
}

const QUICK_ACTIONS = [
  {
    label: "Recent errors",
    query: "Show me recent errors from the last 24 hours",
  },
  {
    label: "Today's captures",
    query: "How many captures were processed today and what were the results?",
  },
  {
    label: "System health",
    query: "Give me a system health overview",
  },
];

/**
 * Quick action chips shown when the investigation chat is empty.
 * Each chip sends a pre-defined query to the investigation agent.
 * Chips disappear after the first message is sent (handled by parent).
 */
export function QuickActionChips({ onSelect }: QuickActionChipsProps) {
  return (
    <View style={styles.container}>
      <Text style={styles.label}>Quick actions</Text>
      <View style={styles.row}>
        {QUICK_ACTIONS.map((action) => (
          <Pressable
            key={action.label}
            style={styles.chip}
            onPress={() => onSelect(action.query)}
          >
            <Text style={styles.chipText}>{action.label}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 16,
    alignItems: "center",
  },
  label: {
    color: "#888888",
    fontSize: 14,
    marginBottom: 12,
  },
  row: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "center",
    gap: 8,
  },
  chip: {
    backgroundColor: "#1a1a2e",
    borderColor: "#4a90d9",
    borderWidth: 1,
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  chipText: {
    color: "#4a90d9",
    fontSize: 14,
  },
});

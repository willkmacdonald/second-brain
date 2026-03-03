import { Pressable, View, Text, StyleSheet } from "react-native";

export interface SectionConfig {
  type: "shopping" | string;
  title: string;
  count: number;
  data: unknown[];
  key: string;
}

interface StatusSectionRendererProps {
  section: SectionConfig;
  isExpanded: boolean;
  onToggle: () => void;
}

/**
 * Generic section header renderer for the Status screen.
 *
 * Designed for extensibility -- the `type` field on SectionConfig allows
 * future section types (e.g., "tasks", "reminders") to reuse this component.
 *
 * Renders a tappable header with section title, item count, and
 * expand/collapse chevron indicator.
 */
export function StatusSectionRenderer({
  section,
  isExpanded,
  onToggle,
}: StatusSectionRendererProps) {
  return (
    <Pressable onPress={onToggle} style={styles.header}>
      <View style={styles.headerLeft}>
        <Text style={styles.headerTitle}>{section.title}</Text>
        <Text style={styles.headerCount}> ({section.count})</Text>
      </View>
      <Text style={styles.chevron}>{isExpanded ? "\u25BC" : "\u25B6"}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: "#16162b",
    paddingHorizontal: 16,
    paddingVertical: 14,
    marginTop: 4,
  },
  headerLeft: {
    flexDirection: "row",
    alignItems: "center",
    flex: 1,
  },
  headerTitle: {
    fontSize: 16,
    fontWeight: "600",
    color: "#ffffff",
  },
  headerCount: {
    fontSize: 16,
    color: "#999",
  },
  chevron: {
    fontSize: 12,
    color: "#666",
  },
});

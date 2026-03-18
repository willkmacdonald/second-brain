import { Pressable, View, Text, StyleSheet } from "react-native";

export interface SectionConfig {
  type: "errand" | string;
  title: string;
  count: number;
  data: unknown[];
  key: string;
  destinationType?: "physical" | "online" | "unrouted";
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
 * future section types (e.g., "errand", "tasks", "reminders") to reuse this component.
 *
 * Renders a tappable header with section title, item count, and
 * expand/collapse chevron indicator.
 */
export function StatusSectionRenderer({
  section,
  isExpanded,
  onToggle,
}: StatusSectionRendererProps) {
  const headerStyle =
    section.destinationType === "unrouted"
      ? [styles.header, styles.unroutedHeader]
      : styles.header;

  return (
    <Pressable onPress={onToggle} style={headerStyle}>
      <View style={styles.headerLeft}>
        <Text style={styles.headerTitle}>{section.title}</Text>
        {section.destinationType === "online" && (
          <View style={styles.onlineTagContainer}>
            <Text style={styles.onlineTag}>ONLINE</Text>
          </View>
        )}
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
  unroutedHeader: {
    borderLeftWidth: 3,
    borderLeftColor: "#f59e0b",
    backgroundColor: "#1a1a10",
  },
  onlineTagContainer: {
    backgroundColor: "rgba(74, 144, 217, 0.15)",
    borderRadius: 8,
    paddingHorizontal: 6,
    paddingVertical: 2,
    marginLeft: 8,
  },
  onlineTag: {
    fontSize: 10,
    fontWeight: "700",
    color: "#4a90d9",
    letterSpacing: 0.5,
  },
});

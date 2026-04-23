import { Pressable, StyleSheet, Text, View } from "react-native";
import { ChevronDown, ChevronRight } from "lucide-react-native";

import { theme } from "../constants/theme";

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
      {isExpanded ? (
        <ChevronDown size={14} color={theme.colors.textMuted} strokeWidth={1.8} />
      ) : (
        <ChevronRight size={14} color={theme.colors.textMuted} strokeWidth={1.8} />
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: theme.colors.surface,
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
    fontFamily: theme.fonts.bodySemiBold,
    color: theme.colors.text,
  },
  headerCount: {
    fontSize: 10.5,
    fontFamily: theme.fonts.mono,
    color: theme.colors.textMuted,
  },
  unroutedHeader: {
    borderLeftWidth: 3,
    borderLeftColor: theme.colors.warn,
    backgroundColor: theme.colors.surfaceHi,
  },
  onlineTagContainer: {
    backgroundColor: theme.colors.accentDim,
    borderRadius: 8,
    paddingHorizontal: 6,
    paddingVertical: 2,
    marginLeft: 8,
  },
  onlineTag: {
    fontSize: 10,
    fontWeight: "700",
    fontFamily: theme.fonts.mono,
    color: theme.colors.accent,
    letterSpacing: 0.5,
  },
});

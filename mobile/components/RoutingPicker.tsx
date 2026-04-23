import { View, Text, ScrollView, Pressable, StyleSheet } from "react-native";
import { theme } from "../constants/theme";

interface Destination {
  slug: string;
  displayName: string;
  type: string;
}

interface RoutingPickerProps {
  destinations: Destination[];
  onRoute: (destinationSlug: string) => void;
}

/**
 * Inline destination picker shown below unrouted errand items.
 *
 * Displays a horizontal scrollable list of destination chips.
 * Tapping a chip calls onRoute with the destination slug.
 * "Other" is always appended as the last option.
 */
export function RoutingPicker({ destinations, onRoute }: RoutingPickerProps) {
  // Filter out "unrouted" and "other" from picker options
  const options = destinations.filter(
    (d) => d.slug !== "unrouted" && d.slug !== "other",
  );

  return (
    <View style={styles.container}>
      <Text style={styles.label}>Route to:</Text>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.scroll}
      >
        {options.map((dest) => (
          <Pressable
            key={dest.slug}
            style={styles.chip}
            onPress={() => onRoute(dest.slug)}
          >
            <Text style={styles.chipText}>{dest.displayName}</Text>
          </Pressable>
        ))}
        {/* Always include "Other" as last option */}
        <Pressable
          style={[styles.chip, styles.otherChip]}
          onPress={() => onRoute("other")}
        >
          <Text style={[styles.chipText, styles.otherChipText]}>Other</Text>
        </Pressable>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 6,
    gap: 8,
  },
  label: {
    fontSize: 12,
    color: theme.colors.textDim,
    fontWeight: "500",
    fontFamily: theme.fonts.bodyMedium,
  },
  scroll: {
    flexGrow: 0,
  },
  chip: {
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: theme.colors.buckets.Admin.fg + "20",
    backgroundColor: theme.colors.buckets.Admin.bg,
    borderRadius: 999,
    paddingHorizontal: 12,
    paddingVertical: 6,
    marginRight: 8,
  },
  chipText: {
    fontSize: 13,
    color: theme.colors.buckets.Admin.fg,
    fontWeight: "500",
    fontFamily: theme.fonts.bodyMedium,
  },
  otherChip: {
    backgroundColor: "transparent",
    borderColor: theme.colors.hairline,
  },
  otherChipText: {
    color: theme.colors.textDim,
  },
});

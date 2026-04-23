import { Pressable, StyleSheet, Text, View } from "react-native";

import { theme } from "../constants/theme";

export interface DashboardData {
  captureCount: number | null;
  successRate: number | null;
  errorCount: number | null;
  lastErrorAge: string | null;
  loading: boolean;
}

interface DashboardCardsProps {
  data: DashboardData;
  onErrorPress: () => void;
}

/**
 * Row of 3 health metric cards displayed at the top of the Status screen.
 *
 * - Captures (24h): display-only count
 * - Success Rate: display-only percentage
 * - Errors (24h): tappable, deep-links to investigation chat, shows recency
 */
export function DashboardCards({ data, onErrorPress }: DashboardCardsProps) {
  const hasErrors = data.errorCount !== null && data.errorCount > 0;

  const errorDisplay = data.loading
    ? "..."
    : hasErrors
      ? `${data.errorCount} error${data.errorCount !== 1 ? "s" : ""}`
      : "None";

  return (
    <View style={styles.row}>
      {/* Captures (24h) */}
      <View style={styles.card}>
        <Text style={styles.label}>Captures (24h)</Text>
        <Text style={styles.value}>
          {data.loading ? "..." : (data.captureCount ?? "--")}
        </Text>
      </View>

      {/* Success Rate */}
      <View style={styles.card}>
        <Text style={styles.label}>Success Rate</Text>
        <Text style={styles.value}>
          {data.loading
            ? "..."
            : data.successRate !== null
              ? `${data.successRate}%`
              : "--"}
        </Text>
      </View>

      {/* Errors (24h) */}
      <Pressable
        style={[styles.card, hasErrors && styles.cardError]}
        onPress={onErrorPress}
        disabled={!hasErrors}
      >
        <Text style={styles.label}>Errors (24h)</Text>
        <Text
          style={[
            styles.value,
            hasErrors ? styles.errorText : styles.noErrorText,
          ]}
          numberOfLines={1}
        >
          {errorDisplay}
        </Text>
        {hasErrors && data.lastErrorAge && (
          <Text style={styles.recencyText}>last: {data.lastErrorAge}</Text>
        )}
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    gap: 8,
    marginHorizontal: 16,
    marginTop: 12,
    marginBottom: 8,
  },
  card: {
    flex: 1,
    backgroundColor: theme.colors.surface,
    borderRadius: 12,
    padding: 12,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: theme.colors.hairline,
  },
  cardError: {
    borderColor: theme.colors.err + "33",
    borderWidth: 1,
  },
  label: {
    color: theme.colors.textMuted,
    fontSize: 10,
    fontFamily: theme.fonts.mono,
    textTransform: "uppercase",
    letterSpacing: 1.4,
    fontWeight: "600",
    marginBottom: 4,
  },
  value: {
    color: theme.colors.text,
    fontSize: 18,
    fontWeight: "600",
    fontFamily: theme.fonts.body,
  },
  errorText: {
    color: theme.colors.err,
    fontSize: 14,
  },
  noErrorText: {
    color: theme.colors.accent,
  },
  recencyText: {
    color: theme.colors.err,
    fontSize: 10.5,
    fontFamily: theme.fonts.mono,
    opacity: 0.7,
    marginTop: 2,
  },
});

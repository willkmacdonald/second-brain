import { Pressable, StyleSheet, Text, View } from "react-native";

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
    backgroundColor: "#1a1a2e",
    borderRadius: 12,
    padding: 12,
  },
  cardError: {
    borderColor: "#ff6b6b",
    borderWidth: 1,
  },
  label: {
    color: "#888888",
    fontSize: 11,
    textTransform: "uppercase",
    marginBottom: 4,
  },
  value: {
    color: "#ffffff",
    fontSize: 18,
    fontWeight: "600",
  },
  errorText: {
    color: "#ff6b6b",
    fontSize: 14,
  },
  noErrorText: {
    color: "#4a90d9",
  },
  recencyText: {
    color: "#ff6b6b",
    fontSize: 11,
    opacity: 0.7,
    marginTop: 2,
  },
});

import { Pressable, StyleSheet, Text, View } from "react-native";

export interface DashboardData {
  captureCount: number | null;
  successRate: number | null;
  lastError: string | null;
  loading: boolean;
}

interface DashboardCardsProps {
  data: DashboardData;
  onErrorPress: (errorMessage: string) => void;
}

/**
 * Row of 3 health metric cards displayed at the top of the Status screen.
 *
 * - Captures (24h): display-only count
 * - Success Rate: display-only percentage
 * - Last Error: tappable, deep-links to investigation chat
 */
export function DashboardCards({ data, onErrorPress }: DashboardCardsProps) {
  const hasError = data.lastError !== null;

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

      {/* Last Error */}
      <Pressable
        style={[styles.card, hasError && styles.cardError]}
        onPress={() => {
          if (hasError) {
            onErrorPress(data.lastError!);
          }
        }}
        disabled={!hasError}
      >
        <Text style={styles.label}>Last Error</Text>
        <Text
          style={[
            styles.value,
            hasError ? styles.errorText : styles.noErrorText,
          ]}
          numberOfLines={2}
        >
          {data.loading ? "..." : (data.lastError ?? "None")}
        </Text>
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
});

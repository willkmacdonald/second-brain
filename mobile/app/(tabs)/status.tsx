import { useState, useCallback } from "react";
import { View, Text, Pressable, ScrollView, StyleSheet } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useFocusEffect, router } from "expo-router";
import { API_BASE_URL, API_KEY } from "../../constants/config";
import {
  DashboardCards,
  type DashboardData,
} from "../../components/DashboardCards";
import { SpineStatusTile } from "../../components/SpineStatusTile";

/**
 * Compute a human-readable age string from an ISO timestamp.
 * Returns null if the timestamp is null or invalid.
 */
function formatErrorAge(isoTimestamp: string | null): string | null {
  if (!isoTimestamp) return null;
  const diffMs = Date.now() - new Date(isoTimestamp).getTime();
  const diffHours = Math.floor(diffMs / 3_600_000);
  if (diffHours < 1) {
    const diffMins = Math.max(1, Math.floor(diffMs / 60_000));
    return `${diffMins}m ago`;
  }
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${Math.floor(diffHours / 24)}d ago`;
}

/**
 * Status screen -- purely observational dashboard.
 *
 * Shows health metric cards and spine segment tiles.
 * No errands, no tasks, no processing trigger.
 * Gear icon navigates to settings; magnifying glass navigates to investigate.
 */
export default function StatusScreen() {
  const [dashboardData, setDashboardData] = useState<DashboardData>({
    captureCount: null,
    successRate: null,
    errorCount: null,
    lastErrorAge: null,
    loading: true,
  });

  const fetchDashboardData = useCallback(async () => {
    if (!API_KEY) return;

    setDashboardData((prev) => ({ ...prev, loading: true }));

    try {
      const res = await fetch(`${API_BASE_URL}/api/health-summary`, {
        headers: { Authorization: `Bearer ${API_KEY}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setDashboardData({
        captureCount: data.captureCount ?? null,
        successRate: data.successRate ?? null,
        errorCount: data.errorCount ?? null,
        lastErrorAge: formatErrorAge(data.lastErrorTime),
        loading: false,
      });
    } catch {
      setDashboardData({
        captureCount: null,
        successRate: null,
        errorCount: null,
        lastErrorAge: null,
        loading: false,
      });
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      fetchDashboardData();
    }, [fetchDashboardData]),
  );

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.screenHeader}>
        <Text style={styles.screenTitle}>Status</Text>
        <View style={{ flexDirection: "row", gap: 16, alignItems: "center" }}>
          <Pressable onPress={() => router.push("/settings")} hitSlop={8}>
            <Text style={styles.headerIcon}>{"\u2699\uFE0F"}</Text>
          </Pressable>
          <Pressable onPress={() => router.push("/investigate")} hitSlop={8}>
            <Text style={styles.headerIcon}>{"\uD83D\uDD0D"}</Text>
          </Pressable>
        </View>
      </View>
      <ScrollView>
        <DashboardCards
          data={dashboardData}
          onErrorPress={() => {
            router.push({
              pathname: "/investigate",
              params: {
                initialQuery:
                  "Show me the errors from the last 24 hours with full details including error messages and affected captures",
              },
            });
          }}
        />
        <SpineStatusTile segmentId="backend_api" />
        <SpineStatusTile segmentId="classifier" />
        <SpineStatusTile segmentId="admin" />
        <SpineStatusTile segmentId="investigation" />
        <SpineStatusTile segmentId="cosmos" />
        <SpineStatusTile segmentId="external_services" />
        <SpineStatusTile segmentId="mobile_ui" />
        <SpineStatusTile segmentId="mobile_capture" />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0f0f23",
  },
  screenHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 4,
  },
  screenTitle: {
    fontSize: 28,
    fontWeight: "bold",
    color: "#ffffff",
  },
  headerIcon: {
    fontSize: 22,
    color: "#4a90d9",
  },
});

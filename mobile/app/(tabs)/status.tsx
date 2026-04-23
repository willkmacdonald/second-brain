import { useState, useCallback } from "react";
import { View, Text, Pressable, ScrollView, StyleSheet } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useFocusEffect, router } from "expo-router";
import { Settings, Search } from "lucide-react-native";

import { API_BASE_URL, API_KEY } from "../../constants/config";
import { theme } from "../../constants/theme";
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
            <Settings size={22} color={theme.colors.textDim} strokeWidth={1.6} />
          </Pressable>
          <Pressable onPress={() => router.push("/investigate")} hitSlop={8}>
            <Search size={22} color={theme.colors.textDim} strokeWidth={1.6} />
          </Pressable>
        </View>
      </View>
      <ScrollView contentContainerStyle={styles.scrollContent}>
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
        <View style={styles.spineSection}>
          <SpineStatusTile segmentId="mobile_ui" />
          <SpineStatusTile segmentId="mobile_capture" />
          <SpineStatusTile segmentId="backend_api" />
          <SpineStatusTile segmentId="classifier" />
          <SpineStatusTile segmentId="admin" />
          <SpineStatusTile segmentId="investigation" />
          <SpineStatusTile segmentId="external_services" />
          <SpineStatusTile segmentId="cosmos" />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.bg,
  },
  screenHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingHorizontal: 20,
    paddingTop: 8,
    paddingBottom: 4,
  },
  screenTitle: {
    fontFamily: theme.fonts.display,
    fontSize: 36,
    fontWeight: "400",
    fontStyle: "italic",
    letterSpacing: -0.8,
    color: theme.colors.text,
  },
  scrollContent: {
    paddingBottom: 24,
  },
  spineSection: {
    paddingHorizontal: 16,
    marginTop: 8,
  },
});

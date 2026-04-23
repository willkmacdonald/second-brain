import { useState, useCallback, useEffect, useRef } from "react";
import {
  View,
  Text,
  SectionList,
  ActivityIndicator,
  StyleSheet,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useFocusEffect } from "expo-router";
import { API_BASE_URL, API_KEY } from "../../constants/config";
import { reportError } from "../../lib/telemetry";
import { theme } from "../../constants/theme";
import { StatusSectionRenderer } from "../../components/StatusSectionRenderer";
import { ErrandRow } from "../../components/ErrandRow";
import { TaskRow } from "../../components/TaskRow";
import { RoutingPicker } from "../../components/RoutingPicker";

interface ErrandItem {
  id: string;
  name: string;
  destination: string;
  needsRouting?: boolean;
  sourceName?: string;
  sourceUrl?: string;
}

interface TaskItem {
  id: string;
  name: string;
}

interface DestinationInfo {
  slug: string;
  displayName: string;
  type: string;
}

interface AdminNotification {
  inboxItemId: string;
  message: string;
}

type SectionItem = ErrandItem | TaskItem;

interface SectionData {
  type: "errand" | "task";
  title: string;
  count: number;
  data: SectionItem[];
  key: string;
  destinationType?: "physical" | "online" | "unrouted";
}

/**
 * Tasks screen displaying errands grouped by destination + general tasks.
 *
 * Sections start collapsed. Tapping a section header expands/collapses it.
 * Swiping an item left deletes it (optimistic, no confirmation).
 * Data refreshes on tab focus with catch-up polling for Admin Agent processing.
 */
export default function TasksScreen() {
  const [sections, setSections] = useState<SectionData[]>([]);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(),
  );
  const [loading, setLoading] = useState(true);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [processingCount, setProcessingCount] = useState(0);
  const [availableDestinations, setAvailableDestinations] = useState<
    DestinationInfo[]
  >([]);
  const [adminNotifications, setAdminNotifications] = useState<
    AdminNotification[]
  >([]);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchData = useCallback(async () => {
    if (!API_KEY) {
      setLoading(false);
      return;
    }
    try {
      const [errandsRes, tasksRes] = await Promise.all([
        fetch(`${API_BASE_URL}/api/errands`, {
          headers: { Authorization: `Bearer ${API_KEY}` },
        }),
        fetch(`${API_BASE_URL}/api/tasks`, {
          headers: { Authorization: `Bearer ${API_KEY}` },
        }),
      ]);

      const allSections: SectionData[] = [];

      if (errandsRes.ok) {
        const errandsData: {
          destinations: {
            destination: string;
            displayName: string;
            type: string;
            items: ErrandItem[];
            count: number;
          }[];
          totalCount: number;
          processingCount?: number;
          adminNotifications?: AdminNotification[];
        } = await errandsRes.json();

        const errandSections: SectionData[] = errandsData.destinations.map(
          (s) => ({
            type: "errand" as const,
            title: s.displayName,
            count: s.count,
            data: s.items,
            key: s.destination,
            destinationType: s.type as SectionData["destinationType"],
          }),
        );
        allSections.push(...errandSections);
        setProcessingCount(errandsData.processingCount ?? 0);
        setAvailableDestinations(
          errandsData.destinations
            .filter((d) => d.type !== "unrouted")
            .map((d) => ({
              slug: d.destination,
              displayName: d.displayName,
              type: d.type,
            })),
        );
        setAdminNotifications(errandsData.adminNotifications ?? []);
      } else {
        void reportError({
          eventType: "crud_failure",
          message: `Errands load failed: HTTP ${errandsRes.status}`,
          correlationKind: "crud",
          metadata: { operation: "load_errands", status: errandsRes.status },
        });
      }

      if (tasksRes.ok) {
        const tasksData: {
          tasks: TaskItem[];
          totalCount: number;
        } = await tasksRes.json();

        if (tasksData.tasks.length > 0) {
          allSections.push({
            type: "task",
            title: "Tasks",
            count: tasksData.totalCount,
            data: tasksData.tasks,
            key: "tasks",
          });
        }
      } else {
        void reportError({
          eventType: "crud_failure",
          message: `Tasks load failed: HTTP ${tasksRes.status}`,
          correlationKind: "crud",
          metadata: { operation: "load_tasks", status: tasksRes.status },
        });
      }

      setSections(allSections);
      setHasLoaded(true);
    } catch (err) {
      void reportError({
        eventType: "crud_failure",
        message: `Tasks data load failed: ${String(err)}`,
        correlationKind: "crud",
        metadata: { operation: "load_tasks_screen" },
      });
      if (!hasLoaded) setLoading(false);
      return;
    }
    setLoading(false);
  }, [hasLoaded]);

  // Refresh on tab focus + brief catch-up polling.
  // The first GET /api/errands triggers Admin Agent processing as a side
  // effect but returns before processing finishes. Poll a few extra times
  // so newly-processed items appear without requiring a manual refresh.
  const focusPollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const focusPollCountRef = useRef(0);
  const FOCUS_POLLS = 4; // extra polls after each focus
  const POLL_INTERVAL = 3000;

  useFocusEffect(
    useCallback(() => {
      void fetchData();
      focusPollCountRef.current = 0;
      focusPollRef.current = setInterval(() => {
        focusPollCountRef.current += 1;
        if (focusPollCountRef.current >= FOCUS_POLLS) {
          if (focusPollRef.current) {
            clearInterval(focusPollRef.current);
            focusPollRef.current = null;
          }
          return;
        }
        void fetchData();
      }, POLL_INTERVAL);
      return () => {
        if (focusPollRef.current) {
          clearInterval(focusPollRef.current);
          focusPollRef.current = null;
        }
      };
    }, [fetchData]),
  );

  // Continue polling while processing is still active (beyond focus polls)
  useEffect(() => {
    if (processingCount > 0 && !focusPollRef.current) {
      pollingRef.current = setInterval(() => {
        void fetchData();
      }, POLL_INTERVAL);
    } else if (processingCount === 0 && pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [processingCount, fetchData]);

  const toggleSection = useCallback((key: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }, []);

  const optimisticRemove = useCallback(
    (sectionKey: string, itemId: string) => {
      setSections((prev) => {
        const updated = prev
          .map((section) => {
            if (section.key !== sectionKey) return section;
            const filtered = section.data.filter((item) => item.id !== itemId);
            return { ...section, data: filtered, count: filtered.length };
          })
          .filter((section) => section.data.length > 0);
        return updated;
      });
    },
    [],
  );

  const handleDeleteErrand = useCallback(
    (itemId: string, destination: string) => {
      optimisticRemove(destination, itemId);
      void (async () => {
        try {
          const res = await fetch(
            `${API_BASE_URL}/api/errands/${itemId}?destination=${encodeURIComponent(destination)}`,
            {
              method: "DELETE",
              headers: { Authorization: `Bearer ${API_KEY}` },
            },
          );
          if (!res.ok && res.status !== 404) {
            void reportError({
              eventType: "crud_failure",
              message: `Delete errand failed: HTTP ${res.status}`,
              correlationKind: "crud",
              metadata: { operation: "delete_errand", errand_id: itemId },
            });
            void fetchData();
          }
        } catch (err) {
          void reportError({
            eventType: "crud_failure",
            message: `Delete errand failed: ${String(err)}`,
            correlationKind: "crud",
            metadata: { operation: "delete_errand", errand_id: itemId },
          });
          void fetchData();
        }
      })();
    },
    [optimisticRemove, fetchData],
  );

  const handleDeleteTask = useCallback(
    (itemId: string) => {
      optimisticRemove("tasks", itemId);
      void (async () => {
        try {
          const res = await fetch(`${API_BASE_URL}/api/tasks/${itemId}`, {
            method: "DELETE",
            headers: { Authorization: `Bearer ${API_KEY}` },
          });
          if (!res.ok && res.status !== 404) {
            void reportError({
              eventType: "crud_failure",
              message: `Delete task failed: HTTP ${res.status}`,
              correlationKind: "crud",
              metadata: { operation: "delete_task", task_id: itemId },
            });
            void fetchData();
          }
        } catch (err) {
          void reportError({
            eventType: "crud_failure",
            message: `Delete task failed: ${String(err)}`,
            correlationKind: "crud",
            metadata: { operation: "delete_task", task_id: itemId },
          });
          void fetchData();
        }
      })();
    },
    [optimisticRemove, fetchData],
  );

  const handleRouteItem = useCallback(
    (itemId: string, destinationSlug: string) => {
      optimisticRemove("unrouted", itemId);

      void (async () => {
        try {
          const res = await fetch(
            `${API_BASE_URL}/api/errands/${itemId}/route`,
            {
              method: "POST",
              headers: {
                Authorization: `Bearer ${API_KEY}`,
                "Content-Type": "application/json",
              },
              body: JSON.stringify({
                destinationSlug,
                saveRule: true,
              }),
            },
          );
          if (!res.ok && res.status !== 404) {
            void reportError({
              eventType: "crud_failure",
              message: `Route errand failed: HTTP ${res.status}`,
              correlationKind: "crud",
              metadata: { operation: "route_errand", errand_id: itemId },
            });
            void fetchData();
          }
        } catch (err) {
          void reportError({
            eventType: "crud_failure",
            message: `Route errand failed: ${String(err)}`,
            correlationKind: "crud",
            metadata: { operation: "route_errand", errand_id: itemId },
          });
          void fetchData();
        }
      })();
    },
    [optimisticRemove, fetchData],
  );

  const handleDismissNotification = useCallback(
    (inboxItemId: string) => {
      setAdminNotifications((prev) =>
        prev.filter((n) => n.inboxItemId !== inboxItemId),
      );

      void (async () => {
        try {
          const res = await fetch(
            `${API_BASE_URL}/api/errands/notifications/${inboxItemId}/dismiss`,
            {
              method: "POST",
              headers: { Authorization: `Bearer ${API_KEY}` },
            },
          );
          if (!res.ok && res.status !== 404) {
            void reportError({
              eventType: "crud_failure",
              message: `Dismiss notification failed: HTTP ${res.status}`,
              correlationKind: "crud",
              metadata: {
                operation: "dismiss_notification",
                inbox_item_id: inboxItemId,
              },
            });
            void fetchData();
          }
        } catch (err) {
          void reportError({
            eventType: "crud_failure",
            message: `Dismiss notification failed: ${String(err)}`,
            correlationKind: "crud",
            metadata: {
              operation: "dismiss_notification",
              inbox_item_id: inboxItemId,
            },
          });
          void fetchData();
        }
      })();
    },
    [fetchData],
  );

  // Show loading spinner on initial load only
  if (loading && !hasLoaded) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={theme.colors.accent} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.screenHeader}>
        <Text style={styles.screenTitle}>Tasks</Text>
      </View>
      <SectionList
        sections={sections}
        extraData={expandedSections}
        keyExtractor={(item) => item.id}
        ListHeaderComponent={
          <View>
            {adminNotifications.map((n) => (
              <View key={n.inboxItemId} style={styles.notificationBanner}>
                <Text style={styles.notificationText}>{n.message}</Text>
                <View>
                  <Text
                    style={styles.dismissText}
                    onPress={() => handleDismissNotification(n.inboxItemId)}
                  >
                    Dismiss
                  </Text>
                </View>
              </View>
            ))}
            {processingCount > 0 && (
              <View style={styles.processingBanner}>
                <ActivityIndicator size="small" color={theme.colors.accent} />
                <Text style={styles.processingText}>
                  Processing {processingCount} new capture
                  {processingCount !== 1 ? "s" : ""}...
                </Text>
              </View>
            )}
          </View>
        }
        renderSectionHeader={({ section }) => (
          <StatusSectionRenderer
            section={section}
            isExpanded={expandedSections.has(section.key)}
            onToggle={() => toggleSection(section.key)}
          />
        )}
        renderItem={({ item, section }) => {
          if (!expandedSections.has(section.key)) return null;
          if (section.type === "task") {
            return (
              <TaskRow item={item as TaskItem} onDelete={handleDeleteTask} />
            );
          }
          if ((section as SectionData).destinationType === "unrouted") {
            return (
              <View>
                <ErrandRow
                  item={item as ErrandItem}
                  onDelete={handleDeleteErrand}
                />
                <RoutingPicker
                  destinations={availableDestinations}
                  onRoute={(slug) => handleRouteItem(item.id, slug)}
                />
              </View>
            );
          }
          return (
            <ErrandRow
              item={item as ErrandItem}
              onDelete={handleDeleteErrand}
            />
          );
        }}
        ListEmptyComponent={
          !loading ? (
            <View style={styles.empty}>
              <Text style={styles.emptyText}>No tasks</Text>
            </View>
          ) : null
        }
        stickySectionHeadersEnabled={false}
        contentContainerStyle={
          sections.length === 0 ? styles.emptyContainer : undefined
        }
      />
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
    paddingTop: 14,
    paddingBottom: 12,
  },
  screenTitle: {
    fontFamily: theme.fonts.display,
    fontSize: 36,
    fontWeight: "400",
    fontStyle: "italic",
    letterSpacing: -0.8,
    color: theme.colors.text,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  empty: {
    alignItems: "center",
    padding: 32,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: "center",
  },
  emptyText: {
    fontSize: 16,
    fontFamily: theme.fonts.body,
    color: theme.colors.textMuted,
  },
  processingBanner: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: theme.colors.accentDim,
    borderRadius: 10,
    padding: 12,
    marginHorizontal: 16,
    marginTop: 8,
    marginBottom: 4,
    gap: 10,
  },
  processingText: {
    fontSize: 14,
    fontFamily: theme.fonts.body,
    color: theme.colors.accent,
    fontWeight: "500",
  },
  notificationBanner: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: theme.colors.surface,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: theme.colors.hairline,
    borderRadius: 10,
    padding: 12,
    marginHorizontal: 16,
    marginTop: 8,
    marginBottom: 4,
    gap: 12,
  },
  notificationText: {
    fontSize: 14,
    fontFamily: theme.fonts.body,
    color: theme.colors.text,
    flex: 1,
    lineHeight: 20,
  },
  dismissText: {
    fontSize: 13,
    fontFamily: theme.fonts.bodySemiBold,
    color: theme.colors.accent,
    fontWeight: "600",
  },
});

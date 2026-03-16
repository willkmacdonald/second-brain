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
import { StatusSectionRenderer } from "../../components/StatusSectionRenderer";
import { ErrandRow } from "../../components/ErrandRow";

interface ErrandItem {
  id: string;
  name: string;
  destination: string;
}

interface ErrandSectionData {
  type: "errand";
  title: string;
  count: number;
  data: ErrandItem[];
  key: string;
}

/**
 * Status screen displaying errands grouped by destination.
 *
 * Sections start collapsed. Tapping a section header expands/collapses it.
 * Swiping an item left deletes it (optimistic, no confirmation).
 * Data refreshes on tab focus -- no pull-to-refresh, no polling.
 */
export default function StatusScreen() {
  const [sections, setSections] = useState<ErrandSectionData[]>([]);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(),
  );
  const [loading, setLoading] = useState(true);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [processingCount, setProcessingCount] = useState(0);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchErrands = useCallback(async () => {
    if (!API_KEY) {
      setLoading(false);
      return;
    }
    try {
      const res = await fetch(`${API_BASE_URL}/api/errands`, {
        headers: { Authorization: `Bearer ${API_KEY}` },
      });
      if (!res.ok) {
        // On error: keep stale data if available, silently retry next focus
        if (!hasLoaded) setLoading(false);
        return;
      }
      const data: {
        destinations: {
          destination: string;
          displayName: string;
          items: ErrandItem[];
          count: number;
        }[];
        totalCount: number;
        processingCount?: number;
      } = await res.json();

      const mapped: ErrandSectionData[] = data.destinations.map((s) => ({
        type: "errand" as const,
        title: s.displayName,
        count: s.count,
        data: s.items,
        key: s.destination,
      }));

      setSections(mapped);
      setProcessingCount(data.processingCount ?? 0);
      setHasLoaded(true);
    } catch {
      // On error: keep stale data if available
      if (!hasLoaded) setLoading(false);
      return;
    }
    setLoading(false);
  }, [hasLoaded]);

  // Refresh on tab focus
  useFocusEffect(
    useCallback(() => {
      void fetchErrands();
    }, [fetchErrands]),
  );

  // Auto-refresh while processing is active
  useEffect(() => {
    if (processingCount > 0) {
      pollingRef.current = setInterval(() => {
        void fetchErrands();
      }, 3000);
    } else if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
        pollingRef.current = null;
      }
    };
  }, [processingCount, fetchErrands]);

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

  const handleDeleteItem = useCallback(
    (itemId: string, destination: string) => {
      // Optimistic removal: immediately remove item from UI
      setSections((prev) => {
        const updated = prev
          .map((section) => {
            if (section.key !== destination) return section;
            const filtered = section.data.filter((item) => item.id !== itemId);
            return {
              ...section,
              data: filtered,
              count: filtered.length,
            };
          })
          .filter((section) => section.data.length > 0);
        return updated;
      });

      // Fire DELETE request -- on failure, refetch instead of snapshot rollback
      // to avoid stale closure issues with rapid deletes
      void (async () => {
        try {
          const res = await fetch(
            `${API_BASE_URL}/api/errands/${itemId}?destination=${destination}`,
            {
              method: "DELETE",
              headers: { Authorization: `Bearer ${API_KEY}` },
            },
          );
          if (!res.ok && res.status !== 404) {
            // Silently refetch to restore accurate state
            void fetchErrands();
          }
        } catch {
          // Silent rollback via refetch
          void fetchErrands();
        }
      })();
    },
    [fetchErrands],
  );

  // Show loading spinner on initial load only
  if (loading && !hasLoaded) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#4a90d9" />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <SectionList
        sections={sections}
        extraData={expandedSections}
        keyExtractor={(item) => item.id}
        ListHeaderComponent={
          processingCount > 0 ? (
            <View style={styles.processingBanner}>
              <ActivityIndicator size="small" color="#4a90d9" />
              <Text style={styles.processingText}>
                Processing {processingCount} new capture
                {processingCount !== 1 ? "s" : ""}...
              </Text>
            </View>
          ) : null
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
          return (
            <ErrandRow item={item} onDelete={handleDeleteItem} />
          );
        }}
        ListEmptyComponent={
          !loading ? (
            <View style={styles.empty}>
              <Text style={styles.emptyText}>No errands yet</Text>
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
    backgroundColor: "#0f0f23",
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
    color: "#666",
  },
  processingBanner: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#1a1a2e",
    borderWidth: 1,
    borderColor: "#4a90d9",
    borderRadius: 10,
    padding: 12,
    marginHorizontal: 16,
    marginTop: 8,
    marginBottom: 4,
    gap: 10,
  },
  processingText: {
    fontSize: 14,
    color: "#4a90d9",
    fontWeight: "500",
  },
});

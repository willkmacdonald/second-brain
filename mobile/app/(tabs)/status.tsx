import { useState, useCallback } from "react";
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
import { ShoppingListRow } from "../../components/ShoppingListRow";

interface ShoppingItem {
  id: string;
  name: string;
  store: string;
}

interface StoreSectionData {
  type: "shopping";
  title: string;
  count: number;
  data: ShoppingItem[];
  key: string;
}

/**
 * Status screen displaying shopping lists grouped by store.
 *
 * Sections start collapsed. Tapping a section header expands/collapses it.
 * Swiping an item left deletes it (optimistic, no confirmation).
 * Data refreshes on tab focus -- no pull-to-refresh, no polling.
 */
export default function StatusScreen() {
  const [sections, setSections] = useState<StoreSectionData[]>([]);
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(),
  );
  const [loading, setLoading] = useState(true);
  const [hasLoaded, setHasLoaded] = useState(false);

  const fetchShoppingLists = useCallback(async () => {
    if (!API_KEY) {
      setLoading(false);
      return;
    }
    try {
      const res = await fetch(`${API_BASE_URL}/api/shopping-lists`, {
        headers: { Authorization: `Bearer ${API_KEY}` },
      });
      if (!res.ok) {
        // On error: keep stale data if available, silently retry next focus
        if (!hasLoaded) setLoading(false);
        return;
      }
      const data: {
        stores: {
          store: string;
          displayName: string;
          items: ShoppingItem[];
          count: number;
        }[];
        totalCount: number;
      } = await res.json();

      const mapped: StoreSectionData[] = data.stores.map((s) => ({
        type: "shopping" as const,
        title: s.displayName,
        count: s.count,
        data: s.items,
        key: s.store,
      }));

      setSections(mapped);
      setHasLoaded(true);
    } catch {
      // On error: keep stale data if available
      if (!hasLoaded) setLoading(false);
      return;
    }
    setLoading(false);
  }, [hasLoaded]);

  // Refresh on tab focus only -- no pull-to-refresh, no background polling
  useFocusEffect(
    useCallback(() => {
      void fetchShoppingLists();
    }, [fetchShoppingLists]),
  );

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
    (itemId: string, store: string) => {
      // Optimistic removal: immediately remove item from UI
      setSections((prev) => {
        const updated = prev
          .map((section) => {
            if (section.key !== store) return section;
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
            `${API_BASE_URL}/api/shopping-lists/items/${itemId}?store=${store}`,
            {
              method: "DELETE",
              headers: { Authorization: `Bearer ${API_KEY}` },
            },
          );
          if (!res.ok && res.status !== 404) {
            // Silently refetch to restore accurate state
            void fetchShoppingLists();
          }
        } catch {
          // Silent rollback via refetch
          void fetchShoppingLists();
        }
      })();
    },
    [fetchShoppingLists],
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
            <ShoppingListRow item={item} onDelete={handleDeleteItem} />
          );
        }}
        ListEmptyComponent={
          !loading ? (
            <View style={styles.empty}>
              <Text style={styles.emptyText}>No items yet</Text>
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
});

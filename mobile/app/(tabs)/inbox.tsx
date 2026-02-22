import { useState, useEffect, useCallback } from "react";
import {
  View,
  Text,
  FlatList,
  RefreshControl,
  Modal,
  Pressable,
  StyleSheet,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router, useNavigation } from "expo-router";
import { API_BASE_URL, API_KEY } from "../../constants/config";
import { InboxItem } from "../../components/InboxItem";
import type { InboxItemData } from "../../components/InboxItem";

const PAGE_SIZE = 20;

/**
 * Inbox screen displaying all recent captures with classification status.
 *
 * Filed items show a detail card on tap. Pending (low_confidence) items
 * navigate to the conversation screen for HITL resolution.
 */
export default function InboxScreen() {
  const [items, setItems] = useState<InboxItemData[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [selectedItem, setSelectedItem] = useState<InboxItemData | null>(null);
  const navigation = useNavigation();

  const fetchInbox = useCallback(
    async (offset = 0, append = false) => {
      if (!API_KEY) return;
      try {
        const res = await fetch(
          `${API_BASE_URL}/api/inbox?limit=${PAGE_SIZE}&offset=${offset}`,
          {
            headers: { Authorization: `Bearer ${API_KEY}` },
          },
        );
        if (!res.ok) return;
        const data: { items: InboxItemData[]; count: number } =
          await res.json();
        if (append) {
          setItems((prev) => [...prev, ...data.items]);
        } else {
          setItems(data.items);
        }
        setHasMore(data.items.length === PAGE_SIZE);
        // Update badge count on tab
        const pendingCount = append
          ? [...items, ...data.items].filter(
              (i) => i.status === "low_confidence",
            ).length
          : data.items.filter((i) => i.status === "low_confidence").length;
        navigation.setOptions({
          tabBarBadge: pendingCount > 0 ? pendingCount : undefined,
        });
      } catch {
        // Silently fail -- empty list is shown
      }
    },
    [navigation, items],
  );

  useEffect(() => {
    void fetchInbox();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchInbox(0, false);
    setRefreshing(false);
  }, [fetchInbox]);

  const handleLoadMore = useCallback(async () => {
    if (loadingMore || !hasMore) return;
    setLoadingMore(true);
    await fetchInbox(items.length, true);
    setLoadingMore(false);
  }, [loadingMore, hasMore, items.length, fetchInbox]);

  const handleItemPress = useCallback(
    (item: InboxItemData) => {
      if (item.status === "low_confidence") {
        router.push(`/conversation/${item.id}`);
      } else {
        setSelectedItem(item);
      }
    },
    [],
  );

  return (
    <SafeAreaView style={styles.container}>
      <Text style={styles.heading}>Inbox</Text>
      <FlatList
        data={items}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <InboxItem item={item} onPress={() => handleItemPress(item)} />
        )}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={handleRefresh}
            tintColor="#4a90d9"
          />
        }
        onEndReached={handleLoadMore}
        onEndReachedThreshold={0.3}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyTitle}>No captures yet</Text>
            <Text style={styles.emptySubtitle}>
              Tap Capture to add your first thought
            </Text>
          </View>
        }
        contentContainerStyle={items.length === 0 ? styles.emptyContainer : undefined}
      />

      {/* Detail card modal for filed items */}
      <Modal
        visible={selectedItem !== null}
        transparent
        animationType="fade"
        onRequestClose={() => setSelectedItem(null)}
      >
        <Pressable
          style={styles.modalOverlay}
          onPress={() => setSelectedItem(null)}
        >
          <View style={styles.detailCard}>
            <Text style={styles.detailLabel}>Captured Text</Text>
            <Text style={styles.detailText}>{selectedItem?.rawText}</Text>

            <View style={styles.detailRow}>
              <View style={styles.detailCol}>
                <Text style={styles.detailLabel}>Bucket</Text>
                <Text style={styles.detailValue}>
                  {selectedItem?.classificationMeta?.bucket ?? "Unknown"}
                </Text>
              </View>
              <View style={styles.detailCol}>
                <Text style={styles.detailLabel}>Confidence</Text>
                <Text style={styles.detailValue}>
                  {selectedItem?.classificationMeta?.confidence != null
                    ? `${Math.round(selectedItem.classificationMeta.confidence * 100)}%`
                    : "N/A"}
                </Text>
              </View>
            </View>

            <Text style={styles.detailLabel}>Agent Chain</Text>
            <Text style={styles.detailValue}>
              {selectedItem?.classificationMeta?.agentChain?.join(" -> ") ??
                "N/A"}
            </Text>

            <Text style={styles.detailLabel}>Timestamp</Text>
            <Text style={styles.detailValue}>
              {selectedItem?.createdAt
                ? new Date(selectedItem.createdAt).toLocaleString()
                : "N/A"}
            </Text>

            <Pressable
              style={styles.closeButton}
              onPress={() => setSelectedItem(null)}
            >
              <Text style={styles.closeButtonText}>Close</Text>
            </Pressable>
          </View>
        </Pressable>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0f0f23",
  },
  heading: {
    fontSize: 28,
    fontWeight: "700",
    color: "#ffffff",
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 12,
  },
  empty: {
    alignItems: "center",
    padding: 32,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: "center",
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: "600",
    color: "#ffffff",
    marginBottom: 8,
  },
  emptySubtitle: {
    fontSize: 14,
    color: "#666",
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.7)",
    justifyContent: "center",
    alignItems: "center",
  },
  detailCard: {
    backgroundColor: "#1a1a2e",
    borderRadius: 16,
    padding: 20,
    width: "85%",
    maxHeight: "70%",
  },
  detailLabel: {
    fontSize: 11,
    fontWeight: "600",
    color: "#666",
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginTop: 12,
    marginBottom: 4,
  },
  detailText: {
    fontSize: 15,
    color: "#ffffff",
    lineHeight: 22,
  },
  detailRow: {
    flexDirection: "row",
    gap: 16,
  },
  detailCol: {
    flex: 1,
  },
  detailValue: {
    fontSize: 14,
    color: "#ccc",
    lineHeight: 20,
  },
  closeButton: {
    marginTop: 20,
    backgroundColor: "#2a2a4e",
    paddingVertical: 10,
    borderRadius: 8,
    alignItems: "center",
  },
  closeButtonText: {
    color: "#4a90d9",
    fontSize: 15,
    fontWeight: "600",
  },
});

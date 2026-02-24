import { useState, useEffect, useCallback } from "react";
import {
  View,
  Text,
  FlatList,
  RefreshControl,
  Modal,
  Pressable,
  Alert,
  StyleSheet,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useNavigation, useFocusEffect } from "expo-router";
import { API_BASE_URL, API_KEY } from "../../constants/config";
import { sendClarification } from "../../lib/ag-ui-client";
import { InboxItem } from "../../components/InboxItem";
import type { InboxItemData } from "../../components/InboxItem";

const PAGE_SIZE = 20;
const BUCKETS = ["People", "Projects", "Ideas", "Admin"];

/**
 * Inbox screen displaying all recent captures with classification status.
 *
 * All items open a detail card with bucket buttons for recategorization
 * (classified items) or manual resolution (pending items).
 */
export default function InboxScreen() {
  const [items, setItems] = useState<InboxItemData[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [selectedItem, setSelectedItem] = useState<InboxItemData | null>(null);
  const [isRecategorizing, setIsRecategorizing] = useState(false);
  const [recategorizeToast, setRecategorizeToast] = useState<string | null>(null);
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
          setItems((prev) => {
            const existingIds = new Set(prev.map((i) => i.id));
            const newItems = data.items.filter(
              (i: InboxItemData) => !existingIds.has(i.id),
            );
            return [...prev, ...newItems];
          });
        } else {
          setItems(data.items);
        }
        setHasMore(data.items.length === PAGE_SIZE);
      } catch {
        // Silently fail -- empty list is shown
      }
    },
    [],
  );

  // Re-fetch inbox every time the screen gains focus (e.g., returning
  // from conversation screen after filing an item)
  useFocusEffect(
    useCallback(() => {
      void fetchInbox();
    }, [fetchInbox]),
  );

  // Derive badge count from items state so it always reflects current data
  useEffect(() => {
    const isPendingStatus = (s: string) =>
      s === "pending" || s === "low_confidence" || s === "unresolved";
    const pendingCount = items.filter((i) => isPendingStatus(i.status)).length;
    navigation.setOptions({
      tabBarBadge: pendingCount > 0 ? pendingCount : undefined,
    });
  }, [items, navigation]);

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

  const handleDeleteItem = useCallback(
    (itemId: string) => {
      Alert.alert("Delete Item", "This will also remove the filed record.", [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: async () => {
            // Optimistic removal
            setItems((prev) => prev.filter((i) => i.id !== itemId));
            try {
              const res = await fetch(`${API_BASE_URL}/api/inbox/${itemId}`, {
                method: "DELETE",
                headers: { Authorization: `Bearer ${API_KEY}` },
              });
              if (!res.ok && res.status !== 404) {
                // Restore on failure — re-fetch to get accurate state
                void fetchInbox();
              }
            } catch {
              void fetchInbox();
            }
          },
        },
      ]);
    },
    [fetchInbox],
  );

  const handleItemPress = useCallback(
    (item: InboxItemData) => {
      setSelectedItem(item);
    },
    [],
  );

  const handleRecategorize = useCallback(
    async (itemId: string, newBucket: string) => {
      if (isRecategorizing) return;
      setIsRecategorizing(true);

      try {
        const res = await fetch(
          `${API_BASE_URL}/api/inbox/${itemId}/recategorize`,
          {
            method: "PATCH",
            headers: {
              Authorization: `Bearer ${API_KEY}`,
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ new_bucket: newBucket }),
          },
        );

        if (res.ok) {
          // Optimistic UI: update item in list
          setItems((prev) =>
            prev.map((i) =>
              i.id === itemId
                ? {
                    ...i,
                    status: "classified",
                    classificationMeta: i.classificationMeta
                      ? { ...i.classificationMeta, bucket: newBucket }
                      : null,
                  }
                : i,
            ),
          );
          setSelectedItem(null);
          setRecategorizeToast(`Moved to ${newBucket}`);
        }
      } catch {
        // Silently fail -- detail card stays open
      } finally {
        setIsRecategorizing(false);
      }
    },
    [isRecategorizing],
  );

  const handlePendingResolve = useCallback(
    (itemId: string, bucket: string) => {
      if (isRecategorizing) return;
      setIsRecategorizing(true);

      const threadId = `resolve-${itemId}`;
      const cleanup = sendClarification({
        threadId,
        bucket,
        apiKey: API_KEY!,
        inboxItemId: itemId,
        callbacks: {
          onComplete: (result: string) => {
            void result;
            setIsRecategorizing(false);
            // Update item in list optimistically
            setItems((prev) =>
              prev.map((i) =>
                i.id === itemId
                  ? {
                      ...i,
                      status: "classified",
                      classificationMeta: i.classificationMeta
                        ? { ...i.classificationMeta, bucket }
                        : { bucket, confidence: 0.85, agentChain: ["User"] },
                    }
                  : i,
              ),
            );
            setSelectedItem(null);
            setRecategorizeToast(`Filed to ${bucket}`);
          },
          onError: () => {
            setIsRecategorizing(false);
          },
        },
      });
      // Store cleanup for potential unmount
      void cleanup;
    },
    [isRecategorizing],
  );

  // Auto-dismiss recategorize toast after 2 seconds
  useEffect(() => {
    if (!recategorizeToast) return;
    const timer = setTimeout(() => setRecategorizeToast(null), 2000);
    return () => clearTimeout(timer);
  }, [recategorizeToast]);

  return (
    <SafeAreaView style={styles.container}>
      <Text style={styles.heading}>Inbox</Text>
      <FlatList
        data={items}
        keyExtractor={(item) => item.id}
        renderItem={({ item }) => (
          <InboxItem
            item={item}
            onPress={() => handleItemPress(item)}
            onDelete={handleDeleteItem}
          />
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

      {/* Detail card modal for all items */}
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
          <View
            style={styles.detailCard}
            onStartShouldSetResponder={() => true}
          >
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

            {(() => {
              const isPendingItem =
                selectedItem?.status === "pending" ||
                selectedItem?.status === "low_confidence";
              const isClassifiedItem = selectedItem?.status === "classified";
              const showBucketButtons = isPendingItem || isClassifiedItem;

              if (!showBucketButtons) return null;

              return (
                <View style={styles.bucketSection}>
                  <Text style={styles.detailLabel}>
                    {isPendingItem ? "File to bucket" : "Move to bucket"}
                  </Text>
                  <View style={styles.bucketRow}>
                    {BUCKETS.map((bucket) => {
                      const isCurrent =
                        !isPendingItem &&
                        selectedItem?.classificationMeta?.bucket === bucket;
                      return (
                        <Pressable
                          key={bucket}
                          onPress={() =>
                            isPendingItem
                              ? handlePendingResolve(selectedItem!.id, bucket)
                              : handleRecategorize(selectedItem!.id, bucket)
                          }
                          disabled={isCurrent || isRecategorizing}
                          style={({ pressed }) => [
                            styles.bucketButton,
                            isCurrent && styles.bucketButtonCurrent,
                            pressed && !isCurrent && styles.bucketButtonPressed,
                            isRecategorizing && styles.bucketButtonDisabled,
                          ]}
                        >
                          <Text
                            style={[
                              styles.bucketButtonText,
                              isCurrent && styles.bucketButtonTextCurrent,
                            ]}
                          >
                            {bucket}
                          </Text>
                        </Pressable>
                      );
                    })}
                  </View>
                </View>
              );
            })()}

            <Pressable
              style={styles.closeButton}
              onPress={() => setSelectedItem(null)}
            >
              <Text style={styles.closeButtonText}>Close</Text>
            </Pressable>
          </View>
        </Pressable>
      </Modal>

      {recategorizeToast && (
        <View style={styles.toastBar}>
          <Text style={styles.toastText}>{recategorizeToast}</Text>
        </View>
      )}
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
  bucketSection: {
    marginTop: 16,
  },
  bucketRow: {
    flexDirection: "row",
    gap: 8,
    marginTop: 4,
  },
  bucketButton: {
    flex: 1,
    backgroundColor: "#2a2a4e",
    paddingVertical: 10,
    borderRadius: 8,
    alignItems: "center",
  },
  bucketButtonCurrent: {
    backgroundColor: "#4a90d9",
  },
  bucketButtonPressed: {
    opacity: 0.7,
  },
  bucketButtonDisabled: {
    opacity: 0.4,
  },
  bucketButtonText: {
    fontSize: 13,
    fontWeight: "600",
    color: "#ccc",
  },
  bucketButtonTextCurrent: {
    color: "#ffffff",
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
  toastBar: {
    position: "absolute",
    bottom: 40,
    left: 20,
    right: 20,
    backgroundColor: "#1a1a2e",
    borderRadius: 10,
    padding: 12,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#4a90d9",
  },
  toastText: {
    color: "#4ade80",
    fontSize: 14,
    fontWeight: "500",
  },
});

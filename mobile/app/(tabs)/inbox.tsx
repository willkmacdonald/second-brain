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
import { reportError } from "../../lib/telemetry";
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
  const [feedbackState, setFeedbackState] = useState<"none" | "thumbs_up" | "thumbs_down">("none");
  const [feedbackToast, setFeedbackToast] = useState<string | null>(null);
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
        if (!res.ok) {
          void reportError({
            eventType: "crud_failure",
            message: `Inbox load HTTP ${res.status}`,
            correlationKind: "crud",
            metadata: { operation: "load_inbox", status: res.status },
          });
          return;
        }
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
      } catch (err) {
        void reportError({
          eventType: "crud_failure",
          message: `Inbox load failed: ${String(err)}`,
          correlationKind: "crud",
          metadata: { operation: "load_inbox" },
        });
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
      s === "pending" || s === "low_confidence" || s === "unresolved" || s === "misunderstood";
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
                void reportError({
                  eventType: "crud_failure",
                  message: `Delete inbox item failed: HTTP ${res.status}`,
                  correlationKind: "crud",
                  metadata: { operation: "delete_inbox", inbox_id: itemId },
                });
                void fetchInbox();
              }
            } catch (err) {
              void reportError({
                eventType: "crud_failure",
                message: `Delete inbox item failed: ${String(err)}`,
                correlationKind: "crud",
                metadata: { operation: "delete_inbox", inbox_id: itemId },
              });
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
      setFeedbackState("none");
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

        if (!res.ok) {
          void reportError({
            eventType: "crud_failure",
            message: `Recategorize failed: HTTP ${res.status}`,
            correlationKind: "crud",
            metadata: {
              operation: "recategorize",
              inbox_id: itemId,
              new_bucket: newBucket,
            },
          });
        }
      } catch (err) {
        void reportError({
          eventType: "crud_failure",
          message: `Recategorize failed: ${String(err)}`,
          correlationKind: "crud",
          metadata: { operation: "recategorize", inbox_id: itemId },
        });
      } finally {
        setIsRecategorizing(false);
      }
    },
    [isRecategorizing],
  );

  const handlePendingResolve = useCallback(
    async (itemId: string, bucket: string) => {
      // Instant confirm via PATCH -- same as recategorize, no SSE streaming
      await handleRecategorize(itemId, bucket);
    },
    [handleRecategorize],
  );

  const handleFeedback = useCallback(
    async (type: "thumbs_up" | "thumbs_down") => {
      const newState = feedbackState === type ? "none" : type;
      setFeedbackState(newState);
      if (newState === "none" || !selectedItem) return;

      setFeedbackToast("Feedback recorded");

      // Fire-and-forget per D-02
      try {
        await fetch(`${API_BASE_URL}/api/feedback`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${API_KEY}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            inboxItemId: selectedItem.id,
            signalType: newState,
            captureText: selectedItem.rawText ?? "",
            originalBucket:
              selectedItem.classificationMeta?.bucket ?? "Unknown",
            captureTraceId: selectedItem.captureTraceId ?? null,
          }),
        });
      } catch {
        // Silent failure per D-02 -- do not show error to user
        void reportError({
          eventType: "crud_failure",
          message: "Feedback submit failed",
          correlationKind: "crud",
          metadata: { operation: "submit_feedback" },
        });
      }
    },
    [feedbackState, selectedItem],
  );

  // Auto-dismiss recategorize toast after 2 seconds
  useEffect(() => {
    if (!recategorizeToast) return;
    const timer = setTimeout(() => setRecategorizeToast(null), 2000);
    return () => clearTimeout(timer);
  }, [recategorizeToast]);

  // Auto-dismiss feedback toast after 2 seconds
  useEffect(() => {
    if (!feedbackToast) return;
    const timer = setTimeout(() => setFeedbackToast(null), 2000);
    return () => clearTimeout(timer);
  }, [feedbackToast]);

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

            {selectedItem?.classificationMeta ? (
              <>
                <View style={styles.detailRow}>
                  <View style={styles.detailCol}>
                    <Text style={styles.detailLabel}>Bucket</Text>
                    <Text style={styles.detailValue}>
                      {selectedItem.classificationMeta.bucket}
                    </Text>
                  </View>
                  <View style={styles.detailCol}>
                    <Text style={styles.detailLabel}>Confidence</Text>
                    <Text style={styles.detailValue}>
                      {Math.round(selectedItem.classificationMeta.confidence * 100)}%
                    </Text>
                  </View>
                </View>
                <Text style={styles.detailLabel}>Agent Chain</Text>
                <Text style={styles.detailValue}>
                  {selectedItem.classificationMeta.agentChain?.join(" -> ") ?? "N/A"}
                </Text>
              </>
            ) : (
              <>
                <Text style={styles.detailLabel}>Status</Text>
                <Text style={[styles.detailValue, { color: selectedItem?.status === "unresolved" ? "#ef4444" : "#f97316" }]}>
                  {selectedItem?.status === "unresolved" ? "Unresolved" : "Needs Clarification"}
                </Text>
                {selectedItem?.clarificationText && (
                  <>
                    <Text style={styles.detailLabel}>Agent Question</Text>
                    <Text style={styles.detailValue}>{selectedItem.clarificationText}</Text>
                  </>
                )}
              </>
            )}

            <Text style={styles.detailLabel}>Timestamp</Text>
            <Text style={styles.detailValue}>
              {selectedItem?.createdAt
                ? new Date(selectedItem.createdAt).toLocaleString()
                : "N/A"}
            </Text>

            {/* Feedback */}
            <Text style={styles.detailLabel}>Feedback</Text>
            <View style={styles.feedbackRow}>
              <Pressable
                onPress={() => handleFeedback("thumbs_down")}
                accessibilityLabel="Rate classification as bad"
                accessibilityRole="button"
                accessibilityState={{ selected: feedbackState === "thumbs_down" }}
                style={({ pressed }) => [
                  styles.feedbackButton,
                  feedbackState === "thumbs_down" && styles.feedbackButtonNegative,
                  pressed && { opacity: 0.7 },
                ]}
              >
                <Text
                  style={[
                    styles.feedbackIcon,
                    { opacity: feedbackState === "thumbs_down" ? 1.0 : 0.5 },
                  ]}
                >
                  {"👎"}
                </Text>
              </Pressable>
              <Pressable
                onPress={() => handleFeedback("thumbs_up")}
                accessibilityLabel="Rate classification as good"
                accessibilityRole="button"
                accessibilityState={{ selected: feedbackState === "thumbs_up" }}
                style={({ pressed }) => [
                  styles.feedbackButton,
                  feedbackState === "thumbs_up" && styles.feedbackButtonPositive,
                  pressed && { opacity: 0.7 },
                ]}
              >
                <Text
                  style={[
                    styles.feedbackIcon,
                    { opacity: feedbackState === "thumbs_up" ? 1.0 : 0.5 },
                  ]}
                >
                  {"👍"}
                </Text>
              </Pressable>
            </View>

            {(() => {
              const isPendingItem =
                selectedItem?.status === "pending" ||
                selectedItem?.status === "low_confidence" ||
                selectedItem?.status === "misunderstood" ||
                selectedItem?.status === "unresolved";
              const isClassifiedItem = selectedItem?.status === "classified";
              // Always show bucket buttons -- all items can be manually categorized

              return (
                <View style={styles.bucketSection}>
                  <Text style={styles.detailLabel}>
                    {isClassifiedItem ? "Move to bucket" : "File to bucket"}
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

      {feedbackToast && (
        <View style={styles.toastBar}>
          <Text style={styles.toastText}>{feedbackToast}</Text>
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
  feedbackRow: {
    flexDirection: "row",
    gap: 12,
    marginTop: 4,
  },
  feedbackButton: {
    width: 56,
    height: 44,
    backgroundColor: "#2a2a4e",
    borderRadius: 12,
    alignItems: "center",
    justifyContent: "center",
  },
  feedbackButtonPositive: {
    backgroundColor: "rgba(74,222,128,0.2)",
    borderWidth: 1,
    borderColor: "#4ade80",
  },
  feedbackButtonNegative: {
    backgroundColor: "rgba(255,107,107,0.2)",
    borderWidth: 1,
    borderColor: "#ff6b6b",
  },
  feedbackIcon: {
    fontSize: 22,
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

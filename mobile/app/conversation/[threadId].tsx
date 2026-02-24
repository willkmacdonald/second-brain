import { useState, useEffect, useCallback } from "react";
import {
  View,
  Text,
  Pressable,
  ActivityIndicator,
  StyleSheet,
  ScrollView,
} from "react-native";
import { useLocalSearchParams, router, Stack } from "expo-router";
import { sendClarification } from "../../lib/ag-ui-client";
import { API_BASE_URL, API_KEY } from "../../constants/config";
import type { InboxItemData } from "../../components/InboxItem";

const BUCKETS = ["People", "Projects", "Ideas", "Admin"];

/**
 * Conversation screen for resolving pending (low_confidence) captures.
 *
 * Accessed by tapping a pending item in the Inbox. Shows the original text,
 * the agent's clarifying question, and 4 bucket buttons for manual classification.
 */
export default function ConversationScreen() {
  const { threadId } = useLocalSearchParams<{ threadId: string }>();
  const [item, setItem] = useState<InboxItemData | null>(null);
  const [loading, setLoading] = useState(true);
  const [isResolving, setIsResolving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [streamedText, setStreamedText] = useState("");

  useEffect(() => {
    if (!threadId) return;
    void fetchItem();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threadId]);

  async function fetchItem() {
    if (!API_KEY) {
      setError("No API key configured");
      setLoading(false);
      return;
    }
    try {
      const res = await fetch(`${API_BASE_URL}/api/inbox/${threadId}`, {
        headers: { Authorization: `Bearer ${API_KEY}` },
      });
      if (!res.ok) {
        setError("Could not load this capture");
        setLoading(false);
        return;
      }
      const data: InboxItemData = await res.json();
      setItem(data);
    } catch {
      setError("Could not load this capture");
    } finally {
      setLoading(false);
    }
  }

  const handleBucketSelect = useCallback(
    (bucket: string) => {
      if (!threadId || isResolving) return;
      setIsResolving(true);
      setStreamedText("");

      const cleanup = sendClarification({
        threadId,
        bucket,
        apiKey: API_KEY,
        inboxItemId: item?.id,
        callbacks: {
          onTextDelta: (delta: string) => {
            setStreamedText((prev) => prev + delta);
          },
          onComplete: () => {
            setIsResolving(false);
            router.back();
          },
          onError: (errorMsg: string) => {
            setIsResolving(false);
            // Check for expired session
            if (
              errorMsg.includes("not found") ||
              errorMsg.includes("expired") ||
              errorMsg.includes("404")
            ) {
              setError("This capture needs to be resubmitted");
            } else {
              setError("Could not file. Try again.");
            }
          },
        },
      });

      // Cleanup on unmount if still in flight
      return () => cleanup();
    },
    [threadId, isResolving, item],
  );

  if (loading) {
    return (
      <View style={styles.container}>
        <Stack.Screen options={{ headerTitle: "Resolve" }} />
        <ActivityIndicator size="large" color="#4a90d9" style={styles.loader} />
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.container}>
        <Stack.Screen options={{ headerTitle: "Resolve" }} />
        <View style={styles.centered}>
          <Text style={styles.errorText}>{error}</Text>
          <Pressable style={styles.backButton} onPress={() => router.back()}>
            <Text style={styles.backButtonText}>Back to Inbox</Text>
          </Pressable>
        </View>
      </View>
    );
  }

  // Use stored clarification text from the classifier, fall back to generic
  const question = item?.clarificationText
    || "Which bucket does this belong to?";

  // Derive top 2 buckets from classification scores
  const topBuckets: string[] = [];
  if (item?.classificationMeta?.allScores) {
    const scores = item.classificationMeta.allScores;
    const sorted = Object.entries(scores).sort(([, a], [, b]) => b - a);
    if (sorted.length >= 2) {
      topBuckets.push(sorted[0][0], sorted[1][0]);
    }
  }

  return (
    <View style={styles.container}>
      <Stack.Screen options={{ headerTitle: "Resolve" }} />
      <ScrollView contentContainerStyle={styles.scrollContent}>
        {/* Original captured text */}
        <View style={styles.quoteCard}>
          <Text style={styles.quoteLabel}>Captured Text</Text>
          <Text style={styles.quoteText}>{item?.rawText}</Text>
        </View>

        {/* Agent question */}
        <Text style={styles.questionText}>{question}</Text>

        {/* Bucket selection buttons */}
        <View style={styles.bucketGrid}>
          {BUCKETS.map((bucket) => {
            const isTopBucket = topBuckets.includes(bucket);
            return (
              <Pressable
                key={bucket}
                onPress={() => handleBucketSelect(bucket)}
                disabled={isResolving}
                style={({ pressed }) => [
                  isTopBucket ? styles.bucketButtonPrimary : styles.bucketButtonSecondary,
                  pressed && styles.bucketPressed,
                  isResolving && styles.bucketDisabled,
                ]}
              >
                <Text style={isTopBucket ? styles.bucketTextPrimary : styles.bucketTextSecondary}>
                  {bucket}
                </Text>
              </Pressable>
            );
          })}
        </View>

        {/* Filing progress */}
        {isResolving && (
          <View style={styles.filingStatus}>
            <ActivityIndicator size="small" color="#4a90d9" />
            <Text style={styles.filingText}>
              {streamedText || "Filing..."}
            </Text>
          </View>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0f0f23",
  },
  loader: {
    marginTop: 40,
  },
  centered: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: 20,
  },
  errorText: {
    fontSize: 16,
    color: "#f87171",
    textAlign: "center",
    marginBottom: 20,
  },
  backButton: {
    backgroundColor: "#2a2a4e",
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 8,
  },
  backButtonText: {
    color: "#4a90d9",
    fontSize: 15,
    fontWeight: "600",
  },
  scrollContent: {
    padding: 16,
  },
  quoteCard: {
    backgroundColor: "#1a1a2e",
    borderRadius: 12,
    padding: 16,
    borderLeftWidth: 3,
    borderLeftColor: "#4a90d9",
    marginBottom: 24,
  },
  quoteLabel: {
    fontSize: 11,
    fontWeight: "600",
    color: "#666",
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginBottom: 8,
  },
  quoteText: {
    fontSize: 16,
    color: "#ffffff",
    lineHeight: 24,
  },
  questionText: {
    fontSize: 17,
    color: "#ccc",
    textAlign: "center",
    marginBottom: 20,
    lineHeight: 24,
  },
  bucketGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
  },
  bucketButtonPrimary: {
    width: "47%",
    backgroundColor: "#4a90d9",
    paddingVertical: 18,
    borderRadius: 12,
    alignItems: "center",
  },
  bucketButtonSecondary: {
    width: "47%",
    backgroundColor: "transparent",
    paddingVertical: 18,
    borderRadius: 12,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#4a4a6e",
  },
  bucketPressed: {
    opacity: 0.7,
    backgroundColor: "#4a90d9",
  },
  bucketDisabled: {
    opacity: 0.4,
  },
  bucketTextPrimary: {
    fontSize: 16,
    fontWeight: "600",
    color: "#ffffff",
  },
  bucketTextSecondary: {
    fontSize: 16,
    fontWeight: "600",
    color: "#888",
  },
  filingStatus: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    marginTop: 20,
  },
  filingText: {
    fontSize: 14,
    color: "#4a90d9",
  },
});

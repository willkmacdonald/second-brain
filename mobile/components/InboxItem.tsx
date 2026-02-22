import { Pressable, View, Text, StyleSheet } from "react-native";

export interface InboxItemData {
  id: string;
  rawText: string;
  title: string | null;
  status: string;
  createdAt: string;
  classificationMeta: {
    bucket: string;
    confidence: number;
    agentChain: string[];
  } | null;
}

interface InboxItemProps {
  item: InboxItemData;
  onPress: () => void;
}

/**
 * Convert an ISO date string to a human-readable relative time string.
 * No library needed -- simple thresholds for MVP.
 */
function getRelativeTime(dateString: string): string {
  const now = Date.now();
  const then = new Date(dateString).getTime();
  const diffMs = now - then;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffSec < 60) return "just now";
  if (diffMin < 60) return `${diffMin} min ago`;
  if (diffHr < 24) return `${diffHr} hr ago`;
  if (diffDay === 1) return "yesterday";
  if (diffDay < 7) return `${diffDay}d ago`;
  return new Date(dateString).toLocaleDateString();
}

/**
 * Inbox list item with text preview, bucket label, relative time,
 * and an orange dot indicator for pending (low_confidence) items.
 */
export function InboxItem({ item, onPress }: InboxItemProps) {
  const isPending = item.status === "low_confidence";
  const bucketLabel = isPending
    ? "Pending"
    : item.classificationMeta?.bucket ?? "Unknown";
  const preview = item.title || item.rawText.slice(0, 60);

  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [styles.row, pressed && styles.rowPressed]}
    >
      {isPending && <View style={styles.orangeDot} />}
      <View style={styles.content}>
        <Text style={styles.preview} numberOfLines={2}>
          {preview}
        </Text>
        <View style={styles.meta}>
          <Text style={[styles.bucket, isPending && styles.bucketPending]}>
            {bucketLabel}
          </Text>
          <Text style={styles.time}>{getRelativeTime(item.createdAt)}</Text>
        </View>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#1a1a2e",
    borderRadius: 10,
    padding: 14,
    marginHorizontal: 16,
    marginVertical: 4,
  },
  rowPressed: {
    opacity: 0.7,
  },
  orangeDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: "#f97316",
    marginRight: 10,
  },
  content: {
    flex: 1,
  },
  preview: {
    fontSize: 15,
    color: "#ffffff",
    lineHeight: 20,
    marginBottom: 4,
  },
  meta: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  bucket: {
    fontSize: 12,
    fontWeight: "600",
    color: "#4a90d9",
  },
  bucketPending: {
    color: "#f97316",
  },
  time: {
    fontSize: 12,
    color: "#666",
  },
});

import { useRef } from "react";
import { Pressable, View, Text, StyleSheet, Animated } from "react-native";
import { Swipeable } from "react-native-gesture-handler";

export interface InboxItemData {
  id: string;
  rawText: string;
  title: string | null;
  status: string;
  createdAt: string;
  clarificationText?: string;
  classificationMeta: {
    bucket: string;
    confidence: number;
    agentChain: string[];
    allScores?: Record<string, number>;
  } | null;
}

interface InboxItemProps {
  item: InboxItemData;
  onPress: () => void;
  onDelete?: (id: string) => void;
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
 * Render the red "Delete" action revealed on right-to-left swipe.
 */
function renderRightActions(
  _progress: Animated.AnimatedInterpolation<number>,
  dragX: Animated.AnimatedInterpolation<number>,
) {
  const opacity = dragX.interpolate({
    inputRange: [-80, -40, 0],
    outputRange: [1, 0.6, 0],
    extrapolate: "clamp",
  });

  return (
    <Animated.View style={[styles.deleteAction, { opacity }]}>
      <Text style={styles.deleteText}>Delete</Text>
    </Animated.View>
  );
}

/**
 * Inbox list item with text preview, bucket label, relative time,
 * and an orange dot indicator for pending (low_confidence) items.
 * Supports right-to-left swipe to reveal delete action.
 */
export function InboxItem({ item, onPress, onDelete }: InboxItemProps) {
  const swipeableRef = useRef<Swipeable>(null);
  const isPending = item.status === "pending" || item.status === "low_confidence";
  const bucketLabel = isPending
    ? "Pending"
    : item.classificationMeta?.bucket ?? "Unknown";
  const preview = item.title || item.rawText.slice(0, 60);

  const handleSwipeOpen = () => {
    swipeableRef.current?.close();
    onDelete?.(item.id);
  };

  return (
    <Swipeable
      ref={swipeableRef}
      renderRightActions={renderRightActions}
      onSwipeableOpen={handleSwipeOpen}
      rightThreshold={80}
      overshootRight={false}
    >
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
    </Swipeable>
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
  deleteAction: {
    backgroundColor: "#dc2626",
    justifyContent: "center",
    alignItems: "center",
    width: 80,
    borderRadius: 10,
    marginVertical: 4,
    marginRight: 16,
  },
  deleteText: {
    color: "#ffffff",
    fontSize: 14,
    fontWeight: "600",
  },
});

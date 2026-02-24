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
 * Determine the status dot color based on item classification status.
 * Orange for items needing user attention, red for agent-abandoned items,
 * null (no dot) for successfully classified items.
 */
function getStatusDotColor(status: string): string | null {
  switch (status) {
    case "pending":
    case "low_confidence":
    case "misunderstood":
      return "#f97316"; // Orange -- needs user attention
    case "unresolved":
      return "#ef4444"; // Red -- agent gave up
    default:
      return null; // No dot for classified/other
  }
}

/**
 * Inbox list item with text preview, bucket label, relative time,
 * and color-coded status dot indicator.
 * Supports right-to-left swipe to reveal delete action.
 */
export function InboxItem({ item, onPress, onDelete }: InboxItemProps) {
  const swipeableRef = useRef<Swipeable>(null);
  const dotColor = getStatusDotColor(item.status);
  const isPending = item.status === "pending" || item.status === "low_confidence" || item.status === "misunderstood";
  const isUnresolved = item.status === "unresolved";
  const bucketLabel = isPending
    ? "Pending"
    : isUnresolved
      ? "Unresolved"
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
        {dotColor && (
          <View style={[styles.statusDot, { backgroundColor: dotColor }]} />
        )}
        <View style={styles.content}>
          <Text style={styles.preview} numberOfLines={2}>
            {preview}
          </Text>
          <View style={styles.meta}>
            <Text style={[styles.bucket, isPending && styles.bucketPending, isUnresolved && styles.bucketUnresolved]}>
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
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
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
  bucketUnresolved: {
    color: "#ef4444",
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

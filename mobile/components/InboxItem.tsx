import { useRef } from "react";
import {
  Pressable,
  View,
  Text,
  StyleSheet,
  Animated,
} from "react-native";
import { Swipeable } from "react-native-gesture-handler";
import { theme, BucketName } from "../constants/theme";

export interface InboxItemData {
  id: string;
  rawText: string;
  title: string | null;
  status: string;
  createdAt: string;
  clarificationText?: string;
  adminProcessingStatus?: string | null;
  captureTraceId?: string | null;
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
      return theme.colors.warn;
    case "unresolved":
      return theme.colors.err;
    default:
      return null; // No dot for classified/other
  }
}

/**
 * Resolve the bucket name to a theme bucket key for color lookup.
 * Falls back to Admin colors for unknown buckets.
 */
function getBucketColors(bucketName: string): {
  fg: string;
  bg: string;
  dot: string;
} {
  const key = bucketName as BucketName;
  return theme.colors.buckets[key] ?? theme.colors.buckets.Admin;
}

/**
 * Inbox list item with text preview, bucket label, relative time,
 * and color-coded status dot indicator.
 * Supports right-to-left swipe to reveal delete action.
 */
export function InboxItem({ item, onPress, onDelete }: InboxItemProps) {
  const swipeableRef = useRef<Swipeable>(null);
  const dotColor = getStatusDotColor(item.status);
  const isMisunderstood = item.status === "misunderstood";
  const isPending =
    item.status === "pending" || item.status === "low_confidence";
  const isUnresolved = item.status === "unresolved";
  const bucketLabel = isMisunderstood
    ? "Needs Clarification"
    : isPending
      ? "Pending"
      : isUnresolved
        ? "Unresolved"
        : item.classificationMeta?.bucket ?? "Unknown";
  const preview =
    item.title && item.title !== "Untitled"
      ? item.title
      : item.rawText.slice(0, 60);

  // Per-bucket colors for the bucket label
  const bucketColors = getBucketColors(
    item.classificationMeta?.bucket ?? "Admin",
  );
  const bucketLabelColor =
    isMisunderstood || isPending
      ? theme.colors.warn
      : isUnresolved
        ? theme.colors.err
        : bucketColors.fg;

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
            <View style={styles.metaLeft}>
              <Text
                style={[styles.bucket, { color: bucketLabelColor }]}
              >
                {bucketLabel.toLowerCase()}
              </Text>
              {item.adminProcessingStatus === "failed" && (
                <Text style={styles.processingFailed}>Processing failed</Text>
              )}
              <Text style={styles.separatorDot}>{"·"}</Text>
              <Text style={styles.time}>
                {getRelativeTime(item.createdAt)}
              </Text>
            </View>
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
    paddingVertical: 12,
    paddingHorizontal: 20,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: theme.colors.hairline,
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
    fontSize: 13.5,
    lineHeight: 19,
    color: theme.colors.text,
    letterSpacing: -0.15,
    fontFamily: theme.fonts.body,
    marginBottom: 5,
  },
  meta: {
    flexDirection: "row",
    alignItems: "center",
  },
  metaLeft: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  processingFailed: {
    fontSize: 10.5,
    color: theme.colors.err,
    fontWeight: "500",
    fontFamily: theme.fonts.mono,
  },
  bucket: {
    fontSize: 10.5,
    fontFamily: theme.fonts.mono,
    letterSpacing: 0.2,
  },
  separatorDot: {
    fontSize: 10.5,
    color: theme.colors.textFaint,
  },
  time: {
    fontSize: 10.5,
    fontFamily: theme.fonts.mono,
    color: theme.colors.textMuted,
    fontVariantNumeric: "tabular-nums",
  },
  deleteAction: {
    backgroundColor: theme.colors.err,
    justifyContent: "center",
    alignItems: "center",
    width: 80,
  },
  deleteText: {
    color: theme.colors.text,
    fontSize: 14,
    fontWeight: "600",
  },
});

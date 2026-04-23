import { useRef } from "react";
import { View, Text, StyleSheet, Animated, Linking, Pressable } from "react-native";
import { Swipeable } from "react-native-gesture-handler";
import { theme } from "../constants/theme";

interface ErrandRowProps {
  item: {
    id: string;
    name: string;
    destination: string;
    sourceName?: string;
    sourceUrl?: string;
  };
  onDelete: (itemId: string, destination: string) => void;
}

/**
 * Render the red "Delete" action revealed on right-to-left swipe.
 * Follows the same pattern as InboxItem.tsx.
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
 * Swipeable errand item row.
 * Displays item name (includes quantity per CONTEXT.md).
 * Swipe left to delete -- no confirmation dialog, no haptic feedback.
 */
export function ErrandRow({ item, onDelete }: ErrandRowProps) {
  const swipeableRef = useRef<Swipeable>(null);

  const handleSwipeOpen = () => {
    swipeableRef.current?.close();
    onDelete(item.id, item.destination);
  };

  return (
    <Swipeable
      ref={swipeableRef}
      renderRightActions={renderRightActions}
      onSwipeableOpen={handleSwipeOpen}
      rightThreshold={80}
      overshootRight={false}
    >
      <View style={styles.row}>
        <Text style={styles.itemName}>{item.name}</Text>
        {item.sourceName && (
          <Pressable
            onPress={() => item.sourceUrl && Linking.openURL(item.sourceUrl)}
          >
            <Text style={styles.sourceText}>from: {item.sourceName}</Text>
          </Pressable>
        )}
      </View>
    </Swipeable>
  );
}

const styles = StyleSheet.create({
  row: {
    backgroundColor: theme.colors.surface,
    borderRadius: 12,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: theme.colors.hairline,
    padding: 14,
    marginHorizontal: 16,
    marginVertical: 2,
  },
  itemName: {
    fontFamily: theme.fonts.body,
    fontSize: 15,
    color: theme.colors.text,
    lineHeight: 20,
    letterSpacing: -0.15,
  },
  sourceText: {
    fontFamily: theme.fonts.mono,
    fontSize: 10.5,
    color: theme.colors.textMuted,
    marginTop: 2,
  },
  deleteAction: {
    backgroundColor: theme.colors.err,
    justifyContent: "center",
    alignItems: "center",
    width: 80,
    borderRadius: 12,
    marginVertical: 2,
    marginRight: 16,
  },
  deleteText: {
    color: theme.colors.text,
    fontSize: 14,
    fontFamily: theme.fonts.bodySemiBold,
    fontWeight: "600",
  },
});

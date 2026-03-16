import { useRef } from "react";
import { View, Text, StyleSheet, Animated } from "react-native";
import { Swipeable } from "react-native-gesture-handler";

interface ErrandRowProps {
  item: { id: string; name: string; destination: string };
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
      </View>
    </Swipeable>
  );
}

const styles = StyleSheet.create({
  row: {
    backgroundColor: "#1a1a2e",
    borderRadius: 10,
    padding: 14,
    marginHorizontal: 16,
    marginVertical: 2,
  },
  itemName: {
    fontSize: 15,
    color: "#ffffff",
    lineHeight: 20,
  },
  deleteAction: {
    backgroundColor: "#dc2626",
    justifyContent: "center",
    alignItems: "center",
    width: 80,
    borderRadius: 10,
    marginVertical: 2,
    marginRight: 16,
  },
  deleteText: {
    color: "#ffffff",
    fontSize: 14,
    fontWeight: "600",
  },
});

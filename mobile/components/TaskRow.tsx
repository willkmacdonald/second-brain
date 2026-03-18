import { useRef } from "react";
import { View, Text, StyleSheet, Animated } from "react-native";
import { Swipeable } from "react-native-gesture-handler";

interface TaskRowProps {
  item: { id: string; name: string };
  onDelete: (itemId: string) => void;
}

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
      <Text style={styles.deleteText}>Done</Text>
    </Animated.View>
  );
}

export function TaskRow({ item, onDelete }: TaskRowProps) {
  const swipeableRef = useRef<Swipeable>(null);

  const handleSwipeOpen = () => {
    swipeableRef.current?.close();
    onDelete(item.id);
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
    backgroundColor: "#16a34a",
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

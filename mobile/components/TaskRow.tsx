import { useRef } from "react";
import { View, Text, StyleSheet, Animated } from "react-native";
import { Swipeable } from "react-native-gesture-handler";
import { theme } from "../constants/theme";

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
    fontSize: 13.5,
    color: theme.colors.text,
    lineHeight: 19,
    letterSpacing: -0.15,
  },
  deleteAction: {
    backgroundColor: theme.colors.ok,
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

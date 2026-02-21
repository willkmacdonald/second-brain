import { Pressable, Text, StyleSheet } from "react-native";
import * as Haptics from "expo-haptics";

interface CaptureButtonProps {
  label: string;
  icon: string;
  onPress: () => void;
  disabled?: boolean;
}

export function CaptureButton({
  label,
  icon,
  onPress,
  disabled,
}: CaptureButtonProps) {
  const handlePress = () => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    onPress();
  };

  return (
    <Pressable
      onPress={handlePress}
      disabled={disabled}
      style={({ pressed }) => [
        styles.button,
        pressed && styles.pressed,
        disabled && styles.disabled,
      ]}
    >
      <Text style={styles.icon}>{icon}</Text>
      <Text style={styles.label}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#1a1a2e",
    borderRadius: 16,
    marginVertical: 6,
  },
  pressed: {
    opacity: 0.7,
    transform: [{ scale: 0.96 }],
  },
  disabled: {
    opacity: 0.4,
  },
  icon: {
    fontSize: 48,
    marginBottom: 8,
  },
  label: {
    fontSize: 20,
    fontWeight: "600",
    color: "#ffffff",
  },
});

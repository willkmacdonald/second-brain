import { Text, StyleSheet, TextStyle } from "react-native";
import { theme } from "../constants/theme";

interface CapsLabelProps {
  children: React.ReactNode;
  color?: string;
  size?: number;
  style?: TextStyle;
}

export function CapsLabel({
  children,
  color = theme.colors.textMuted,
  size = 10,
  style,
}: CapsLabelProps) {
  return (
    <Text
      style={[
        styles.label,
        { color, fontSize: size, letterSpacing: size < 11 ? 1.4 : 1.2 },
        style,
      ]}
    >
      {children}
    </Text>
  );
}

const styles = StyleSheet.create({
  label: {
    fontFamily: theme.fonts.bodySemiBold,
    fontWeight: "600",
    textTransform: "uppercase",
  },
});

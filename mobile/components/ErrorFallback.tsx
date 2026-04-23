import { View, Text, Pressable, StyleSheet } from "react-native";
import { theme } from "../constants/theme";

interface ErrorFallbackProps {
  error: unknown;
  componentStack: string | null;
  resetError: () => void;
  eventId: string;
}

export function ErrorFallback({ error, resetError }: ErrorFallbackProps) {
  const message = error instanceof Error ? error.message : String(error);

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Something went wrong</Text>
      <Text style={styles.message}>{message}</Text>
      <Pressable style={styles.button} onPress={resetError}>
        <Text style={styles.buttonText}>Try Again</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.bg,
    justifyContent: "center",
    alignItems: "center",
    padding: 24,
  },
  title: {
    color: theme.colors.text,
    fontSize: 20,
    fontWeight: "400",
    fontFamily: theme.fonts.display,
    fontStyle: "italic",
    marginBottom: 12,
  },
  message: {
    color: theme.colors.textDim,
    fontSize: 14,
    fontFamily: theme.fonts.body,
    textAlign: "center",
    marginBottom: 24,
  },
  button: {
    backgroundColor: theme.colors.accent,
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 8,
  },
  buttonText: {
    color: theme.colors.text,
    fontSize: 16,
    fontWeight: "600",
    fontFamily: theme.fonts.bodySemiBold,
  },
});

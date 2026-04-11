import { View, Text, Pressable, StyleSheet } from "react-native";

interface ErrorFallbackProps {
  error: Error;
  componentStack: string | null;
  resetError: () => void;
  eventId: string;
}

export function ErrorFallback({ error, resetError }: ErrorFallbackProps) {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Something went wrong</Text>
      <Text style={styles.message}>{error.message}</Text>
      <Pressable style={styles.button} onPress={resetError}>
        <Text style={styles.buttonText}>Try Again</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0f0f23",
    justifyContent: "center",
    alignItems: "center",
    padding: 24,
  },
  title: { color: "#ffffff", fontSize: 20, fontWeight: "bold", marginBottom: 12 },
  message: { color: "#999999", fontSize: 14, textAlign: "center", marginBottom: 24 },
  button: {
    backgroundColor: "#4a90d9",
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 8,
  },
  buttonText: { color: "#ffffff", fontSize: 16, fontWeight: "600" },
});

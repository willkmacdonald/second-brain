import { useState, useEffect, useRef, useCallback } from "react";
import {
  View,
  TextInput,
  Pressable,
  Text,
  StyleSheet,
} from "react-native";
import * as Haptics from "expo-haptics";
import { Stack } from "expo-router";
import { sendCapture } from "../../lib/ag-ui-client";
import { API_KEY } from "../../constants/config";

interface Toast {
  message: string;
  type: "success" | "error";
}

export default function TextCaptureScreen() {
  const [thought, setThought] = useState("");
  const [sending, setSending] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);
  const cleanupRef = useRef<(() => void) | null>(null);

  // Clear toast after 2 seconds
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 2000);
    return () => clearTimeout(timer);
  }, [toast]);

  // Cleanup SSE connection on unmount
  useEffect(() => {
    return () => {
      if (cleanupRef.current) {
        cleanupRef.current();
        cleanupRef.current = null;
      }
    };
  }, []);

  const handleSubmit = useCallback(() => {
    if (!thought.trim() || sending) return;

    if (!API_KEY) {
      setToast({ message: "No API key configured", type: "error" });
      return;
    }

    setSending(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);

    const cleanup = sendCapture({
      message: thought.trim(),
      apiKey: API_KEY,
      onComplete: (result: string) => {
        setSending(false);
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
        setToast({ message: result || "Captured", type: "success" });
        setThought("");
      },
      onError: (error: string) => {
        void error; // Show generic message per locked CONTEXT.md decision
        setSending(false);
        setToast({
          message: "Couldn\u2019t file your capture. Try again.",
          type: "error",
        });
      },
    });

    cleanupRef.current = cleanup;
  }, [thought, sending]);

  const sendDisabled = !thought.trim() || sending;

  return (
    <View style={styles.container}>
      <Stack.Screen
        options={{
          headerTitle: () =>
            toast ? (
              <Text
                style={[
                  styles.headerToast,
                  toast.type === "success"
                    ? styles.headerToastSuccess
                    : styles.headerToastError,
                ]}
              >
                {toast.message}
              </Text>
            ) : (
              <Text style={styles.headerTitle}>Text Input</Text>
            ),
          headerRight: () => (
            <Pressable
              onPress={handleSubmit}
              disabled={sendDisabled}
              style={({ pressed }) => [
                styles.headerSendButton,
                pressed && styles.sendPressed,
                sendDisabled && styles.sendDisabled,
              ]}
            >
              <Text style={[styles.headerSendText, sendDisabled && styles.headerSendTextDisabled]}>
                {sending ? "Sending..." : "Send"}
              </Text>
            </Pressable>
          ),
        }}
      />

      <TextInput
        style={styles.input}
        value={thought}
        onChangeText={setThought}
        placeholder="What's on your mind?"
        placeholderTextColor="#666"
        multiline
        autoFocus
        textAlignVertical="top"
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0f0f23",
    padding: 16,
  },
  input: {
    flex: 1,
    fontSize: 18,
    color: "#ffffff",
    padding: 16,
    backgroundColor: "#1a1a2e",
    borderRadius: 12,
    textAlignVertical: "top",
  },
  headerTitle: {
    color: "#ffffff",
    fontSize: 17,
    fontWeight: "600",
  },
  headerToast: {
    fontSize: 14,
    fontWeight: "500",
  },
  headerToastSuccess: {
    color: "#4ade80",
  },
  headerToastError: {
    color: "#f87171",
  },
  headerSendButton: {
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  sendPressed: {
    opacity: 0.7,
  },
  sendDisabled: {
    opacity: 0.4,
  },
  headerSendText: {
    color: "#4a90d9",
    fontSize: 17,
    fontWeight: "600",
  },
  headerSendTextDisabled: {
    color: "#666",
  },
});

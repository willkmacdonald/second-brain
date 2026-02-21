import { useState, useEffect, useRef, useCallback } from "react";
import {
  View,
  TextInput,
  Pressable,
  Text,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import * as Haptics from "expo-haptics";
import { router } from "expo-router";
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
      onComplete: () => {
        setSending(false);
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
        setToast({ message: "Sent", type: "success" });
        setTimeout(() => {
          router.back();
        }, 500);
      },
      onError: (error: string) => {
        void error; // Fire-and-forget: show generic message per locked decision
        setSending(false);
        setToast({
          message: "Couldn\u2019t send \u2014 check connection",
          type: "error",
        });
      },
    });

    cleanupRef.current = cleanup;
  }, [thought, sending]);

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
    >
      <View style={styles.inputContainer}>
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

      <Pressable
        onPress={handleSubmit}
        disabled={!thought.trim() || sending}
        style={({ pressed }) => [
          styles.sendButton,
          pressed && styles.sendPressed,
          (!thought.trim() || sending) && styles.sendDisabled,
        ]}
      >
        <Text style={styles.sendText}>
          {sending ? "Sending..." : "Send"}
        </Text>
      </Pressable>

      {toast ? (
        <View
          style={[
            styles.toast,
            toast.type === "success" ? styles.toastSuccess : styles.toastError,
          ]}
        >
          <Text style={styles.toastText}>{toast.message}</Text>
        </View>
      ) : null}
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0f0f23",
    padding: 16,
  },
  inputContainer: {
    flex: 1,
    marginBottom: 12,
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
  sendButton: {
    backgroundColor: "#4a90d9",
    padding: 16,
    borderRadius: 12,
    alignItems: "center",
    marginBottom: 8,
  },
  sendPressed: {
    opacity: 0.7,
  },
  sendDisabled: {
    opacity: 0.4,
  },
  sendText: {
    color: "#ffffff",
    fontSize: 18,
    fontWeight: "600",
  },
  toast: {
    position: "absolute",
    bottom: 32,
    left: 16,
    right: 16,
    padding: 12,
    borderRadius: 8,
    alignItems: "center",
  },
  toastSuccess: {
    backgroundColor: "#2d7d46",
  },
  toastError: {
    backgroundColor: "#c0392b",
  },
  toastText: {
    color: "#ffffff",
    fontSize: 14,
    fontWeight: "500",
  },
});

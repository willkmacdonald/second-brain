import { useState, useEffect, useRef, useCallback } from "react";
import {
  View,
  TextInput,
  Pressable,
  Text,
  StyleSheet,
  ScrollView,
} from "react-native";
import * as Haptics from "expo-haptics";
import { Stack } from "expo-router";
import { sendCapture, sendClarification } from "../../lib/ag-ui-client";
import { API_KEY } from "../../constants/config";
import { AgentSteps } from "../../components/AgentSteps";

const AGENT_STEPS = ["Orchestrator", "Classifier"];
const BUCKETS = ["People", "Projects", "Ideas", "Admin"];
const AUTO_RESET_MS = 2500;

interface Toast {
  message: string;
  type: "success" | "error";
}

export default function TextCaptureScreen() {
  const [thought, setThought] = useState("");
  const [sending, setSending] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);
  const [currentStep, setCurrentStep] = useState<string | null>(null);
  const [completedSteps, setCompletedSteps] = useState<string[]>([]);
  const [streamedText, setStreamedText] = useState("");
  const [showSteps, setShowSteps] = useState(false);
  const [hitlQuestion, setHitlQuestion] = useState<string | null>(null);
  const [hitlThreadId, setHitlThreadId] = useState<string | null>(null);
  const [hitlInboxItemId, setHitlInboxItemId] = useState<string | null>(null);
  const [hitlTopBuckets, setHitlTopBuckets] = useState<string[]>([]);
  const [isResolving, setIsResolving] = useState(false);
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

  const resetState = useCallback(() => {
    setThought("");
    setShowSteps(false);
    setCurrentStep(null);
    setCompletedSteps([]);
    setStreamedText("");
    setHitlQuestion(null);
    setHitlThreadId(null);
    setHitlInboxItemId(null);
    setHitlTopBuckets([]);
  }, []);

  const handleSubmit = useCallback(() => {
    if (!thought.trim() || sending) return;

    if (!API_KEY) {
      setToast({ message: "No API key configured", type: "error" });
      return;
    }

    // If HITL is pending, clear it -- pending item stays in inbox for later resolution
    if (hitlThreadId) {
      setHitlQuestion(null);
      setHitlThreadId(null);
      setHitlInboxItemId(null);
      setHitlTopBuckets([]);
      setStreamedText("");
      setShowSteps(false);
      setCurrentStep(null);
      setCompletedSteps([]);
    }

    setSending(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);

    const captureResult = sendCapture({
      message: thought.trim(),
      apiKey: API_KEY,
      callbacks: {
        onStepStart: (stepName: string) => {
          setShowSteps(true);
          setCurrentStep(stepName);
        },
        onStepFinish: (stepName: string) => {
          setCompletedSteps((prev) => [...prev, stepName]);
          setCurrentStep(null);
        },
        onTextDelta: (delta: string) => {
          setStreamedText((prev) => prev + delta);
        },
        onHITLRequired: (threadId: string, questionText: string, inboxItemId?: string) => {
          setHitlThreadId(threadId);
          setHitlQuestion(questionText);
          setHitlInboxItemId(inboxItemId ?? null);
          setSending(false); // Re-enable interaction for bucket selection

          // Extract top 2 buckets from questionText pattern
          // The classifier's question contains bucket names -- first 2 mentioned are the top ones
          const mentioned: string[] = [];
          for (const b of BUCKETS) {
            if (questionText.includes(b)) {
              mentioned.push(b);
            }
          }
          setHitlTopBuckets(mentioned.slice(0, 2));
        },
        onComplete: (result: string) => {
          setSending(false);
          Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
          setToast({ message: result || "Captured", type: "success" });
          setTimeout(resetState, AUTO_RESET_MS);
        },
        onError: (error: string) => {
          void error;
          setSending(false);
          setShowSteps(false);
          setToast({
            message: "Couldn\u2019t file your capture. Try again.",
            type: "error",
          });
        },
      },
    });
    cleanupRef.current = captureResult.cleanup;
  }, [thought, sending, hitlThreadId, resetState]);

  const handleBucketSelect = useCallback(
    (bucket: string) => {
      if (!hitlThreadId || isResolving) return;
      setIsResolving(true);
      setHitlQuestion(null); // Hide question UI
      setStreamedText(""); // Clear question text, show filing progress

      const cleanup = sendClarification({
        threadId: hitlThreadId,
        bucket,
        apiKey: API_KEY!,
        inboxItemId: hitlInboxItemId ?? undefined,
        callbacks: {
          onTextDelta: (delta: string) => {
            setStreamedText((prev) => prev + delta);
          },
          onComplete: (result: string) => {
            setIsResolving(false);
            Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
            setToast({ message: result || "Filed", type: "success" });
            setTimeout(resetState, AUTO_RESET_MS);
          },
          onError: () => {
            setIsResolving(false);
            setToast({
              message: "Couldn\u2019t file. Try again.",
              type: "error",
            });
          },
        },
      });
      cleanupRef.current = cleanup;
    },
    [hitlThreadId, hitlInboxItemId, isResolving, resetState],
  );

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
              <Text
                style={[
                  styles.headerSendText,
                  sendDisabled && styles.headerSendTextDisabled,
                ]}
              >
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

      {/* Step dots, streaming text, and HITL area below input */}
      {showSteps && (
        <View style={styles.feedbackArea}>
          <AgentSteps
            steps={AGENT_STEPS}
            currentStep={currentStep}
            completedSteps={completedSteps}
          />

          {streamedText.length > 0 && (
            <ScrollView style={styles.streamContainer}>
              <Text style={styles.streamedText}>{streamedText}</Text>
            </ScrollView>
          )}

          {hitlQuestion !== null && (
            <View style={styles.hitlContainer}>
              <Text style={styles.hitlQuestion}>{hitlQuestion}</Text>
              <View style={styles.bucketRow}>
                {BUCKETS.map((bucket) => {
                  const isTopBucket = hitlTopBuckets.includes(bucket);
                  return (
                    <Pressable
                      key={bucket}
                      onPress={() => handleBucketSelect(bucket)}
                      disabled={isResolving}
                      style={({ pressed }) => [
                        isTopBucket ? styles.bucketButtonPrimary : styles.bucketButtonSecondary,
                        pressed && styles.bucketPressed,
                        isResolving && styles.bucketDisabled,
                      ]}
                    >
                      <Text style={isTopBucket ? styles.bucketTextPrimary : styles.bucketTextSecondary}>
                        {bucket}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
            </View>
          )}

          {isResolving && (
            <Text style={styles.resolvingText}>Filing...</Text>
          )}
        </View>
      )}
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
    fontSize: 18,
    color: "#ffffff",
    padding: 16,
    backgroundColor: "#1a1a2e",
    borderRadius: 12,
    textAlignVertical: "top",
    minHeight: 120,
    maxHeight: 200,
  },
  feedbackArea: {
    marginTop: 12,
    backgroundColor: "#1a1a2e",
    borderRadius: 12,
    padding: 12,
  },
  streamContainer: {
    maxHeight: 100,
    marginTop: 8,
  },
  streamedText: {
    fontSize: 14,
    color: "#999",
    lineHeight: 20,
  },
  hitlContainer: {
    marginTop: 12,
  },
  hitlQuestion: {
    fontSize: 14,
    color: "#ccc",
    lineHeight: 20,
    marginBottom: 12,
    textAlign: "center",
  },
  bucketRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 8,
  },
  bucketButtonPrimary: {
    flex: 1,
    backgroundColor: "#4a90d9",
    paddingVertical: 10,
    paddingHorizontal: 4,
    borderRadius: 8,
    alignItems: "center",
  },
  bucketButtonSecondary: {
    flex: 1,
    backgroundColor: "transparent",
    paddingVertical: 10,
    paddingHorizontal: 4,
    borderRadius: 8,
    alignItems: "center",
    borderWidth: 1,
    borderColor: "#4a4a6e",
  },
  bucketPressed: {
    opacity: 0.7,
    backgroundColor: "#4a90d9",
  },
  bucketDisabled: {
    opacity: 0.4,
  },
  bucketTextPrimary: {
    fontSize: 13,
    fontWeight: "600",
    color: "#ffffff",
  },
  bucketTextSecondary: {
    fontSize: 13,
    fontWeight: "600",
    color: "#888",
  },
  resolvingText: {
    fontSize: 12,
    color: "#4a90d9",
    textAlign: "center",
    marginTop: 8,
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

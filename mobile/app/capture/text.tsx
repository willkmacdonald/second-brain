import { useState, useEffect, useRef, useCallback } from "react";
import {
  View,
  TextInput,
  Pressable,
  Text,
  StyleSheet,
  ScrollView,
  Animated,
} from "react-native";
import {
  useAudioRecorder,
  AudioModule,
  useAudioRecorderState,
  RecordingPresets,
} from "expo-audio";
import * as Haptics from "expo-haptics";
import { Stack } from "expo-router";
import { sendCapture, sendFollowUp, sendFollowUpVoice } from "../../lib/ag-ui-client";
import { API_BASE_URL, API_KEY } from "../../constants/config";
import { AgentSteps } from "../../components/AgentSteps";

const AGENT_STEPS = ["Classifying"];
const BUCKETS = ["People", "Projects", "Ideas", "Admin"];
const AUTO_RESET_MS = 2500;

/** Format milliseconds as M:SS */
function formatDuration(ms: number): string {
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  return `${m}:${(s % 60).toString().padStart(2, "0")}`;
}

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
  const [followUpRound, setFollowUpRound] = useState(0);
  const [agentQuestion, setAgentQuestion] = useState<string | null>(null);
  const [misunderstoodInboxItemId, setMisunderstoodInboxItemId] = useState<string | null>(null);
  const [isReclassifying, setIsReclassifying] = useState(false);
  const [followUpMode, setFollowUpMode] = useState<"voice" | "text">("voice");
  const [isFollowUpRecording, setIsFollowUpRecording] = useState(false);
  const [micPermissionGranted, setMicPermissionGranted] = useState(false);
  const cleanupRef = useRef<(() => void) | null>(null);

  // Audio recorder for voice follow-up
  const audioRecorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const recorderState = useAudioRecorderState(audioRecorder, 100);

  // Clear toast after 2 seconds
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 2000);
    return () => clearTimeout(timer);
  }, [toast]);

  // Request mic permission when entering voice follow-up mode
  useEffect(() => {
    if (followUpMode === "voice" && agentQuestion) {
      AudioModule.requestRecordingPermissionsAsync().then((status) => {
        setMicPermissionGranted(status.granted);
      });
    }
  }, [followUpMode, agentQuestion]);

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
    setFollowUpRound(0);
    setAgentQuestion(null);
    setMisunderstoodInboxItemId(null);
    setIsReclassifying(false);
    setFollowUpMode("voice");
    setIsFollowUpRecording(false);
  }, []);

  const handleFollowUpSubmit = useCallback(() => {
    if (!thought.trim() || isReclassifying || !misunderstoodInboxItemId) return;

    setIsReclassifying(true);
    setShowSteps(true);
    setCurrentStep(null);
    setCompletedSteps([]);
    setStreamedText("");
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);

    const cleanup = sendFollowUp({
      inboxItemId: misunderstoodInboxItemId,
      followUpText: thought.trim(),
      followUpRound: followUpRound,
      apiKey: API_KEY!,
      callbacks: {
        onStepStart: (stepName: string) => {
          setCurrentStep(stepName);
        },
        onStepFinish: (stepName: string) => {
          setCompletedSteps((prev) => [...prev, stepName]);
          setCurrentStep(null);
        },
        onTextDelta: (delta: string) => {
          setStreamedText((prev) => prev + delta);
        },
        onLowConfidence: (_inboxItemId: string, bucket: string, confidence: number) => {
          setIsReclassifying(false);
          Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
          setToast({ message: `Filed -> ${bucket} (${confidence.toFixed(2)})`, type: "success" });
          setTimeout(resetState, AUTO_RESET_MS);
        },
        onMisunderstood: (_threadId: string, questionText: string, _inboxItemId: string) => {
          // Still misunderstood -- show next question
          setAgentQuestion(questionText);
          setFollowUpRound((prev) => prev + 1);
          setThought("");
          setIsReclassifying(false);
          setShowSteps(false);
        },
        onUnresolved: (_inboxItemId: string) => {
          setIsReclassifying(false);
          setToast({ message: "Couldn\u2019t classify. Check inbox later.", type: "error" });
          setTimeout(resetState, AUTO_RESET_MS);
        },
        onComplete: (result: string) => {
          setIsReclassifying(false);
          Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
          setToast({ message: result || "Filed", type: "success" });
          setTimeout(resetState, AUTO_RESET_MS);
        },
        onError: () => {
          setIsReclassifying(false);
          setToast({ message: "Couldn\u2019t classify. Try again.", type: "error" });
        },
      },
    });
    cleanupRef.current = cleanup;
  }, [thought, isReclassifying, misunderstoodInboxItemId, followUpRound, resetState]);

  const handleVoiceFollowUpSubmit = useCallback(async () => {
    if (!misunderstoodInboxItemId || isReclassifying) return;

    await audioRecorder.stop();
    setIsFollowUpRecording(false);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);

    if (recorderState.durationMillis < 1000) {
      return;
    }

    const uri = audioRecorder.uri;
    if (!uri) return;

    if (!API_KEY) {
      setToast({ message: "No API key configured", type: "error" });
      return;
    }

    setIsReclassifying(true);
    setShowSteps(true);
    setCurrentStep(null);
    setCompletedSteps([]);
    setStreamedText("");

    const cleanup = sendFollowUpVoice({
      audioUri: uri,
      inboxItemId: misunderstoodInboxItemId,
      followUpRound: followUpRound,
      apiKey: API_KEY,
      callbacks: {
        onStepStart: (stepName: string) => {
          setCurrentStep(stepName);
        },
        onStepFinish: (stepName: string) => {
          setCompletedSteps((prev) => [...prev, stepName]);
          setCurrentStep(null);
        },
        onTextDelta: (delta: string) => {
          setStreamedText((prev) => prev + delta);
        },
        onLowConfidence: (_inboxItemId: string, bucket: string, confidence: number) => {
          setIsReclassifying(false);
          Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
          setToast({ message: `Filed -> ${bucket} (${confidence.toFixed(2)})`, type: "success" });
          setTimeout(resetState, AUTO_RESET_MS);
        },
        onMisunderstood: (_threadId: string, questionText: string, _inboxItemId: string) => {
          setAgentQuestion(questionText);
          setFollowUpRound((prev) => prev + 1);
          setIsReclassifying(false);
          setShowSteps(false);
        },
        onUnresolved: (_inboxItemId: string) => {
          setIsReclassifying(false);
          setToast({ message: "Couldn\u2019t classify. Check inbox later.", type: "error" });
          setTimeout(resetState, AUTO_RESET_MS);
        },
        onComplete: (result: string) => {
          setIsReclassifying(false);
          Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
          setToast({ message: result || "Filed", type: "success" });
          setTimeout(resetState, AUTO_RESET_MS);
        },
        onError: () => {
          setIsReclassifying(false);
          setToast({ message: "Couldn\u2019t classify. Try again.", type: "error" });
        },
      },
    });
    cleanupRef.current = cleanup;
  }, [misunderstoodInboxItemId, isReclassifying, audioRecorder, recorderState.durationMillis, followUpRound, resetState]);

  const handleFollowUpRecordToggle = useCallback(async () => {
    if (isFollowUpRecording) {
      await handleVoiceFollowUpSubmit();
    } else {
      if (!micPermissionGranted) {
        setToast({ message: "Mic permission required", type: "error" });
        return;
      }
      await audioRecorder.prepareToRecordAsync();
      audioRecorder.record();
      setIsFollowUpRecording(true);
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);
    }
  }, [isFollowUpRecording, micPermissionGranted, audioRecorder, handleVoiceFollowUpSubmit]);

  const handleSubmit = useCallback(() => {
    if (followUpRound > 0 && followUpMode === "text") {
      handleFollowUpSubmit();
      return;
    }

    if (followUpRound > 0) {
      return; // Voice mode handles its own submit
    }

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
        onLowConfidence: (inboxItemId: string, bucket: string, _confidence: number) => {
          // Show bucket buttons for low-confidence classification
          setHitlInboxItemId(inboxItemId);
          setHitlQuestion(`Best guess: ${bucket}. Which bucket?`);
          setShowSteps(true); // CRITICAL: bucket buttons are gated on {showSteps && ...}
          setSending(false);
          setHitlTopBuckets([bucket]);
        },
        onMisunderstood: (threadId: string, questionText: string, inboxItemId: string) => {
          void threadId;
          setAgentQuestion(questionText);
          setMisunderstoodInboxItemId(inboxItemId);
          setFollowUpRound(1);
          setThought(""); // Clear input for user's reply
          setSending(false);
          setShowSteps(false); // Hide step dots during conversation
        },
        onUnresolved: (_inboxItemId: string) => {
          setSending(false);
          setToast({ message: "Couldn\u2019t classify. Check inbox later.", type: "error" });
          setTimeout(resetState, AUTO_RESET_MS);
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
  }, [thought, sending, hitlThreadId, followUpRound, handleFollowUpSubmit, resetState]);

  const handleBucketSelect = useCallback(
    async (bucket: string) => {
      if (!hitlInboxItemId || isResolving) return;
      setIsResolving(true);
      setHitlQuestion(null); // Hide question UI

      try {
        const res = await fetch(
          `${API_BASE_URL}/api/inbox/${hitlInboxItemId}/recategorize`,
          {
            method: "PATCH",
            headers: {
              Authorization: `Bearer ${API_KEY}`,
              "Content-Type": "application/json",
            },
            body: JSON.stringify({ new_bucket: bucket }),
          },
        );
        if (res.ok) {
          Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
          setToast({ message: "Filed", type: "success" });
          setTimeout(resetState, AUTO_RESET_MS);
        } else {
          setToast({ message: "Couldn\u2019t file. Try again.", type: "error" });
        }
      } catch {
        setToast({ message: "Couldn\u2019t file. Try again.", type: "error" });
      } finally {
        setIsResolving(false);
      }
    },
    [hitlInboxItemId, isResolving, resetState],
  );

  const sendDisabled = !thought.trim() || sending || isReclassifying;

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
                {isReclassifying ? "Classifying..." : sending ? "Sending..." : (followUpRound > 0 && followUpMode === "text") ? "Reply" : "Send"}
              </Text>
            </Pressable>
          ),
        }}
      />

      {agentQuestion && (
        <View style={styles.agentQuestionBubble}>
          <Text style={styles.agentQuestionText}>{agentQuestion}</Text>
          <Text style={styles.followUpHint}>
            Reply below (follow-up {followUpRound} of 2)
          </Text>
        </View>
      )}

      {/* Voice-first follow-up for misunderstood captures */}
      {agentQuestion && followUpMode === "voice" && (
        <View style={styles.followUpVoiceArea}>
          {isFollowUpRecording && (
            <Text style={styles.followUpDuration}>
              {formatDuration(recorderState.durationMillis)}
            </Text>
          )}
          <Pressable
            onPress={handleFollowUpRecordToggle}
            disabled={isReclassifying}
            style={({ pressed }) => [
              styles.followUpRecordButton,
              isFollowUpRecording && styles.followUpRecordButtonActive,
              pressed && { opacity: 0.7 },
              isReclassifying && { opacity: 0.4 },
            ]}
          >
            <View
              style={
                isFollowUpRecording
                  ? { width: 18, height: 18, borderRadius: 3, backgroundColor: "#ffffff" }
                  : { width: 18, height: 18, borderRadius: 9, backgroundColor: "#ffffff" }
              }
            />
          </Pressable>
          <Pressable onPress={() => setFollowUpMode("text")}>
            <Text style={styles.followUpToggle}>Type instead</Text>
          </Pressable>
        </View>
      )}

      {/* Text follow-up fallback */}
      {agentQuestion && followUpMode === "text" && (
        <View>
          <TextInput
            style={styles.input}
            value={thought}
            onChangeText={setThought}
            placeholder="Add more context..."
            placeholderTextColor="#666"
            multiline
            autoFocus
            textAlignVertical="top"
          />
          <Pressable onPress={() => setFollowUpMode("voice")}>
            <Text style={styles.followUpToggle}>Record instead</Text>
          </Pressable>
        </View>
      )}

      {/* Normal text input (not in follow-up mode) */}
      {!agentQuestion && (
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
      )}

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
  agentQuestionBubble: {
    backgroundColor: "#1a1a2e",
    borderRadius: 12,
    padding: 14,
    marginBottom: 12,
    borderLeftWidth: 3,
    borderLeftColor: "#4a90d9",
  },
  agentQuestionText: {
    fontSize: 15,
    color: "#ccc",
    lineHeight: 22,
  },
  followUpHint: {
    fontSize: 12,
    color: "#666",
    marginTop: 6,
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
  followUpVoiceArea: {
    alignItems: "center",
    marginBottom: 12,
  },
  followUpRecordButton: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: "#333",
    alignItems: "center",
    justifyContent: "center",
    alignSelf: "center",
    marginTop: 12,
  },
  followUpRecordButtonActive: {
    backgroundColor: "#e53935",
  },
  followUpToggle: {
    color: "#4a90d9",
    fontSize: 13,
    textAlign: "center",
    marginTop: 8,
  },
  followUpDuration: {
    color: "#999",
    fontSize: 13,
    textAlign: "center",
    marginTop: 4,
  },
});

import { useState, useEffect, useRef, useCallback } from "react";
import {
  View,
  TextInput,
  Pressable,
  Text,
  StyleSheet,
  Animated,
  Alert,
  Platform,
  ToastAndroid,
  ActivityIndicator,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import {
  useAudioRecorder,
  AudioModule,
  useAudioRecorderState,
  RecordingPresets,
} from "expo-audio";
import * as Haptics from "expo-haptics";
import {
  sendCapture,
  sendVoiceCapture,
  sendFollowUp,
  sendFollowUpVoice,
} from "../../lib/ag-ui-client";
import { API_BASE_URL, API_KEY } from "../../constants/config";

const BUCKETS = ["People", "Projects", "Ideas", "Admin"];
const AUTO_RESET_MS = 2500;

interface Toast {
  message: string;
  type: "success" | "error";
}

function showToast(message: string) {
  if (Platform.OS === "android") {
    ToastAndroid.show(message, ToastAndroid.SHORT);
  } else {
    Alert.alert(message);
  }
}

/** Format milliseconds as M:SS */
function formatDuration(ms: number): string {
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  return `${m}:${(s % 60).toString().padStart(2, "0")}`;
}

export default function CaptureScreen() {
  const [mode, setMode] = useState<"voice" | "text">("voice");
  const [thought, setThought] = useState("");

  // Voice recording state
  const [isRecording, setIsRecording] = useState(false);
  const [permissionGranted, setPermissionGranted] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);
  const [processingStage, setProcessingStage] = useState<
    "uploading" | "transcribing" | "classifying" | null
  >(null);

  // HITL state
  const [hitlQuestion, setHitlQuestion] = useState<string | null>(null);
  const [hitlThreadId, setHitlThreadId] = useState<string | null>(null);
  const [hitlInboxItemId, setHitlInboxItemId] = useState<string | null>(null);
  const [hitlTopBuckets, setHitlTopBuckets] = useState<string[]>([]);
  const [isResolving, setIsResolving] = useState(false);
  const [followUpRound, setFollowUpRound] = useState(0);
  const [agentQuestion, setAgentQuestion] = useState<string | null>(null);
  const [misunderstoodInboxItemId, setMisunderstoodInboxItemId] = useState<
    string | null
  >(null);
  const [isReclassifying, setIsReclassifying] = useState(false);
  const [followUpText, setFollowUpText] = useState("");

  // Pulsing animation for recording indicator
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const cleanupRef = useRef<(() => void) | null>(null);

  // Audio recorder
  const audioRecorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const recorderState = useAudioRecorderState(audioRecorder, 100);

  // Request mic permission when entering voice mode
  useEffect(() => {
    if (mode !== "voice") return;

    (async () => {
      const status = await AudioModule.requestRecordingPermissionsAsync();
      if (status.granted) {
        setPermissionGranted(true);
        await AudioModule.setAudioModeAsync({
          allowsRecording: true,
          playsInSilentMode: true,
        });
      } else {
        setPermissionGranted(false);
        showToast("Mic permission required");
      }
    })();
  }, [mode]);

  // Pulsing animation during recording
  useEffect(() => {
    if (isRecording) {
      const animation = Animated.loop(
        Animated.sequence([
          Animated.timing(pulseAnim, {
            toValue: 0.3,
            duration: 800,
            useNativeDriver: true,
          }),
          Animated.timing(pulseAnim, {
            toValue: 1,
            duration: 800,
            useNativeDriver: true,
          }),
        ]),
      );
      animation.start();
      return () => animation.stop();
    } else {
      pulseAnim.setValue(1);
    }
  }, [isRecording, pulseAnim]);

  // Clear toast after 2 seconds
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 2000);
    return () => clearTimeout(timer);
  }, [toast]);

  // Cleanup SSE on unmount
  useEffect(() => {
    return () => {
      if (cleanupRef.current) {
        cleanupRef.current();
        cleanupRef.current = null;
      }
    };
  }, []);

  const resetState = useCallback(() => {
    setProcessing(false);
    setProcessingStage(null);
    setThought("");
    setHitlQuestion(null);
    setHitlThreadId(null);
    setHitlInboxItemId(null);
    setHitlTopBuckets([]);
    setFollowUpRound(0);
    setAgentQuestion(null);
    setMisunderstoodInboxItemId(null);
    setIsReclassifying(false);
    setFollowUpText("");
    setMode("voice");
  }, []);

  const handleRecordToggle = useCallback(async () => {
    if (!permissionGranted) {
      showToast("Mic permission required");
      return;
    }

    if (isRecording) {
      // Stop recording
      await audioRecorder.stop();
      setIsRecording(false);
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);

      // Check duration -- discard if < 1 second
      if (recorderState.durationMillis < 1000) {
        return; // Discard silently
      }

      const uri = audioRecorder.uri;
      if (!uri) {
        showToast("Recording failed");
        return;
      }

      if (!API_KEY) {
        setToast({ message: "No API key configured", type: "error" });
        return;
      }

      // Upload and process
      setProcessing(true);
      setProcessingStage("uploading");

      const cleanup = sendVoiceCapture({
        audioUri: uri,
        apiKey: API_KEY,
        callbacks: {
          onStepStart: () => {
            setProcessingStage("classifying");
          },
          onStepFinish: () => {},
          onLowConfidence: (
            inboxItemId: string,
            bucket: string,
            _confidence: number,
          ) => {
            setHitlInboxItemId(inboxItemId);
            setHitlQuestion(`Best guess: ${bucket}. Which bucket?`);
            setProcessing(false);
            setProcessingStage(null);
            setHitlTopBuckets([bucket]);
          },
          onMisunderstood: (
            _threadId: string,
            questionText: string,
            inboxItemId: string,
          ) => {
            setAgentQuestion(questionText);
            setMisunderstoodInboxItemId(inboxItemId);
            setFollowUpRound(1);
            setProcessing(false);
            setProcessingStage(null);
          },
          onUnresolved: (_inboxItemId: string) => {
            setProcessing(false);
            setProcessingStage(null);
            setToast({
              message: "Couldn\u2019t classify. Check inbox later.",
              type: "error",
            });
            setTimeout(resetState, AUTO_RESET_MS);
          },
          onHITLRequired: (
            threadId: string,
            questionText: string,
            inboxItemId?: string,
          ) => {
            setHitlThreadId(threadId);
            setHitlQuestion(questionText);
            setHitlInboxItemId(inboxItemId ?? null);
            setProcessing(false);
            setProcessingStage(null);

            // Extract top 2 buckets from questionText
            const mentioned: string[] = [];
            for (const b of BUCKETS) {
              if (questionText.includes(b)) {
                mentioned.push(b);
              }
            }
            setHitlTopBuckets(mentioned.slice(0, 2));
          },
          onComplete: (result: string) => {
            setProcessing(false);
            setProcessingStage(null);
            Haptics.notificationAsync(
              Haptics.NotificationFeedbackType.Success,
            );
            setToast({ message: result || "Captured", type: "success" });
            setTimeout(resetState, AUTO_RESET_MS);
          },
          onError: (error: string) => {
            console.error("Voice capture error:", error);
            setProcessing(false);
            setProcessingStage(null);
            setToast({
              message: error || "Couldn\u2019t file your capture. Try again.",
              type: "error",
            });
          },
        },
      });
      cleanupRef.current = cleanup;
    } else {
      // Start recording
      await audioRecorder.prepareToRecordAsync();
      audioRecorder.record();
      setIsRecording(true);
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);
    }
  }, [
    isRecording,
    permissionGranted,
    audioRecorder,
    recorderState.durationMillis,
    resetState,
  ]);

  const handleTextSubmit = useCallback(() => {
    if (!thought.trim() || processing) return;
    if (!API_KEY) {
      setToast({ message: "No API key configured", type: "error" });
      return;
    }

    setProcessing(true);
    setProcessingStage("classifying");
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);

    const captureResult = sendCapture({
      message: thought.trim(),
      apiKey: API_KEY,
      callbacks: {
        onStepStart: () => setProcessingStage("classifying"),
        onStepFinish: () => {},
        onLowConfidence: (
          inboxItemId: string,
          bucket: string,
          _confidence: number,
        ) => {
          setHitlInboxItemId(inboxItemId);
          setHitlQuestion(`Best guess: ${bucket}. Which bucket?`);
          setProcessing(false);
          setProcessingStage(null);
          setHitlTopBuckets([bucket]);
        },
        onMisunderstood: (
          _threadId: string,
          questionText: string,
          inboxItemId: string,
        ) => {
          setAgentQuestion(questionText);
          setMisunderstoodInboxItemId(inboxItemId);
          setFollowUpRound(1);
          setThought("");
          setProcessing(false);
          setProcessingStage(null);
        },
        onUnresolved: () => {
          setProcessing(false);
          setProcessingStage(null);
          setToast({
            message: "Couldn\u2019t classify. Check inbox later.",
            type: "error",
          });
          setTimeout(resetState, AUTO_RESET_MS);
        },
        onComplete: (result: string) => {
          setProcessing(false);
          setProcessingStage(null);
          Haptics.notificationAsync(
            Haptics.NotificationFeedbackType.Success,
          );
          setToast({ message: result || "Captured", type: "success" });
          setTimeout(resetState, AUTO_RESET_MS);
        },
        onError: (error: string) => {
          setProcessing(false);
          setProcessingStage(null);
          setToast({
            message: error || "Couldn\u2019t file your capture. Try again.",
            type: "error",
          });
        },
      },
    });
    cleanupRef.current = captureResult.cleanup;
  }, [thought, processing, resetState]);

  const handleFollowUpSubmit = useCallback(() => {
    if (!followUpText.trim() || isReclassifying || !misunderstoodInboxItemId)
      return;

    setIsReclassifying(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);

    const cleanup = sendFollowUp({
      inboxItemId: misunderstoodInboxItemId,
      followUpText: followUpText.trim(),
      followUpRound: followUpRound,
      apiKey: API_KEY,
      callbacks: {
        onStepStart: () => {},
        onStepFinish: () => {},
        onLowConfidence: (
          _inboxItemId: string,
          bucket: string,
          confidence: number,
        ) => {
          setIsReclassifying(false);
          Haptics.notificationAsync(
            Haptics.NotificationFeedbackType.Success,
          );
          setToast({
            message: `Filed -> ${bucket} (${confidence.toFixed(2)})`,
            type: "success",
          });
          setTimeout(resetState, AUTO_RESET_MS);
        },
        onMisunderstood: (
          _threadId: string,
          questionText: string,
          _inboxItemId: string,
        ) => {
          setAgentQuestion(questionText);
          setFollowUpRound((prev) => prev + 1);
          setFollowUpText("");
          setIsReclassifying(false);
        },
        onUnresolved: (_inboxItemId: string) => {
          setIsReclassifying(false);
          setToast({
            message: "Couldn\u2019t classify. Check inbox later.",
            type: "error",
          });
          setTimeout(resetState, AUTO_RESET_MS);
        },
        onComplete: (result: string) => {
          setIsReclassifying(false);
          Haptics.notificationAsync(
            Haptics.NotificationFeedbackType.Success,
          );
          setToast({ message: result || "Filed", type: "success" });
          setTimeout(resetState, AUTO_RESET_MS);
        },
        onError: () => {
          setIsReclassifying(false);
          setToast({
            message: "Couldn\u2019t classify. Try again.",
            type: "error",
          });
        },
      },
    });
    cleanupRef.current = cleanup;
  }, [
    followUpText,
    isReclassifying,
    misunderstoodInboxItemId,
    followUpRound,
    resetState,
  ]);

  const handleVoiceFollowUp = useCallback(async () => {
    if (!misunderstoodInboxItemId || isReclassifying) return;

    // Stop recording
    await audioRecorder.stop();
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);

    // Check duration -- discard if < 1 second
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

    const cleanup = sendFollowUpVoice({
      audioUri: uri,
      inboxItemId: misunderstoodInboxItemId,
      followUpRound: followUpRound,
      apiKey: API_KEY,
      callbacks: {
        onStepStart: () => {},
        onStepFinish: () => {},
        onLowConfidence: (
          _inboxItemId: string,
          bucket: string,
          confidence: number,
        ) => {
          setIsReclassifying(false);
          Haptics.notificationAsync(
            Haptics.NotificationFeedbackType.Success,
          );
          setToast({
            message: `Filed -> ${bucket} (${confidence.toFixed(2)})`,
            type: "success",
          });
          setTimeout(resetState, AUTO_RESET_MS);
        },
        onMisunderstood: (
          _threadId: string,
          questionText: string,
          _inboxItemId: string,
        ) => {
          setAgentQuestion(questionText);
          setFollowUpRound((prev) => prev + 1);
          setIsReclassifying(false);
        },
        onUnresolved: (_inboxItemId: string) => {
          setIsReclassifying(false);
          setToast({
            message: "Couldn\u2019t classify. Check inbox later.",
            type: "error",
          });
          setTimeout(resetState, AUTO_RESET_MS);
        },
        onComplete: (result: string) => {
          setIsReclassifying(false);
          Haptics.notificationAsync(
            Haptics.NotificationFeedbackType.Success,
          );
          setToast({ message: result || "Filed", type: "success" });
          setTimeout(resetState, AUTO_RESET_MS);
        },
        onError: () => {
          setIsReclassifying(false);
          setToast({
            message: "Couldn\u2019t classify. Try again.",
            type: "error",
          });
        },
      },
    });
    cleanupRef.current = cleanup;
  }, [
    misunderstoodInboxItemId,
    isReclassifying,
    audioRecorder,
    recorderState.durationMillis,
    followUpRound,
    resetState,
  ]);

  const handleFollowUpRecordToggle = useCallback(async () => {
    if (!permissionGranted) {
      showToast("Mic permission required");
      return;
    }

    if (isRecording) {
      setIsRecording(false);
      await handleVoiceFollowUp();
    } else {
      await audioRecorder.prepareToRecordAsync();
      audioRecorder.record();
      setIsRecording(true);
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);
    }
  }, [isRecording, permissionGranted, audioRecorder, handleVoiceFollowUp]);

  const handleBucketSelect = useCallback(
    async (bucket: string) => {
      if (!hitlInboxItemId || isResolving) return;
      setIsResolving(true);
      setHitlQuestion(null);

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
          Haptics.notificationAsync(
            Haptics.NotificationFeedbackType.Success,
          );
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

  // Whether recording controls should be disabled
  const recordDisabled = processing || isResolving || isReclassifying;

  return (
    <SafeAreaView style={styles.container}>
      {/* Toast overlay */}
      {toast && (
        <View
          style={[
            styles.toastContainer,
            toast.type === "success"
              ? styles.toastSuccess
              : styles.toastError,
          ]}
        >
          <Text style={styles.toastText}>{toast.message}</Text>
        </View>
      )}

      {/* Voice/Text toggle row -- ALWAYS visible */}
      <View style={styles.toggleRow}>
        <Pressable
          style={[
            styles.toggleButton,
            mode === "voice" && styles.toggleActive,
          ]}
          onPress={() => setMode("voice")}
        >
          <Text style={styles.toggleIcon}>{"\uD83C\uDF99\uFE0F"}</Text>
          <Text style={styles.toggleLabel}>Voice</Text>
        </Pressable>
        <Pressable
          style={[
            styles.toggleButton,
            mode === "text" && styles.toggleActive,
          ]}
          onPress={() => setMode("text")}
        >
          <Text style={styles.toggleIcon}>{"\u270D\uFE0F"}</Text>
          <Text style={styles.toggleLabel}>Text</Text>
        </Pressable>
      </View>

      {/* Main content area */}
      <View style={styles.contentArea}>
        {/* Agent question bubble -- shown during HITL follow-up */}
        {agentQuestion && (
          <View style={styles.agentQuestionBubble}>
            <Text style={styles.agentQuestionText}>{agentQuestion}</Text>
            <Text style={styles.followUpHint}>
              Reply below (follow-up {followUpRound} of 2)
            </Text>
          </View>
        )}

        {/* Processing stage indicator -- replaces record button/text input during processing */}
        {processingStage && (
          <View style={styles.processingArea}>
            <ActivityIndicator size="large" color="#4a90d9" />
            <Text style={styles.processingStageText}>
              {processingStage === "uploading"
                ? "Uploading..."
                : processingStage === "classifying"
                  ? "Classifying..."
                  : "Processing..."}
            </Text>
          </View>
        )}

        {/* Voice mode content (record button, timer) -- hidden during processing and HITL question */}
        {mode === "voice" && !processingStage && !agentQuestion && (
          <View style={styles.voiceArea}>
            {/* Timer -- visible only during recording */}
            {isRecording && (
              <Text style={styles.timer}>
                {formatDuration(recorderState.durationMillis)}
              </Text>
            )}

            {/* Record button with pulsing ring */}
            <View style={styles.recordContainer}>
              {isRecording && (
                <Animated.View
                  style={[styles.pulseRing, { opacity: pulseAnim }]}
                />
              )}
              <Pressable
                onPress={handleRecordToggle}
                disabled={recordDisabled}
                style={({ pressed }) => [
                  styles.recordButton,
                  isRecording && styles.recordButtonActive,
                  pressed && styles.recordPressed,
                  recordDisabled && styles.recordDisabled,
                ]}
              >
                <View
                  style={
                    isRecording ? styles.recordStopIcon : styles.recordMicIcon
                  }
                />
              </Pressable>
            </View>

            {/* Status text */}
            {!isRecording && !processing && (
              <Text style={styles.voiceHint}>
                {permissionGranted
                  ? "Tap to record"
                  : "Mic permission required"}
              </Text>
            )}
          </View>
        )}

        {/* Text mode content (text input + send button) -- hidden during processing */}
        {mode === "text" && !processingStage && !agentQuestion && (
          <View style={styles.textInputContainer}>
            <TextInput
              style={styles.textInput}
              value={thought}
              onChangeText={setThought}
              placeholder="What's on your mind?"
              placeholderTextColor="#666"
              multiline
              autoFocus
              textAlignVertical="top"
            />
            <Pressable
              onPress={handleTextSubmit}
              disabled={!thought.trim() || processing}
              style={({ pressed }) => [
                styles.sendButton,
                pressed && { opacity: 0.7 },
                (!thought.trim() || processing) && { opacity: 0.4 },
              ]}
            >
              <Text style={styles.sendButtonText}>
                {processing ? "..." : "Send"}
              </Text>
            </Pressable>
          </View>
        )}

        {/* Voice follow-up (record button for reply) -- shown during HITL follow-up in voice mode */}
        {agentQuestion && mode === "voice" && (
          <View style={styles.followUpVoiceArea}>
            {isRecording && (
              <Text style={styles.followUpDuration}>
                {formatDuration(recorderState.durationMillis)}
              </Text>
            )}
            <Pressable
              onPress={handleFollowUpRecordToggle}
              disabled={isReclassifying}
              style={({ pressed }) => [
                styles.followUpRecordButton,
                isRecording && styles.followUpRecordButtonActive,
                pressed && { opacity: 0.7 },
                isReclassifying && styles.recordDisabled,
              ]}
            >
              <View
                style={
                  isRecording ? styles.recordStopIcon : styles.recordMicIcon
                }
              />
            </Pressable>
          </View>
        )}

        {/* Text follow-up (text input for reply) -- shown during HITL follow-up in text mode */}
        {agentQuestion && mode === "text" && (
          <View style={styles.followUpRow}>
            <TextInput
              style={styles.followUpInput}
              value={followUpText}
              onChangeText={setFollowUpText}
              placeholder="Add more context..."
              placeholderTextColor="#666"
              multiline
            />
            <Pressable
              onPress={handleFollowUpSubmit}
              disabled={!followUpText.trim() || isReclassifying}
              style={({ pressed }) => [
                styles.followUpSendButton,
                pressed && styles.sendPressed,
                (!followUpText.trim() || isReclassifying) &&
                  styles.sendDisabled,
              ]}
            >
              <Text
                style={[
                  styles.followUpSendText,
                  (!followUpText.trim() || isReclassifying) &&
                    styles.sendTextDisabled,
                ]}
              >
                {isReclassifying ? "..." : "Reply"}
              </Text>
            </Pressable>
          </View>
        )}

        {/* Bucket selection buttons -- shown for low-confidence classification */}
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
                      isTopBucket
                        ? styles.bucketButtonPrimary
                        : styles.bucketButtonSecondary,
                      pressed && styles.bucketPressed,
                      isResolving && styles.bucketDisabled,
                    ]}
                  >
                    <Text
                      style={
                        isTopBucket
                          ? styles.bucketTextPrimary
                          : styles.bucketTextSecondary
                      }
                    >
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
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0f0f23",
  },
  toggleRow: {
    flexDirection: "row",
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 8,
    gap: 12,
  },
  toggleButton: {
    flex: 1,
    height: 72,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "#1a1a2e",
    borderRadius: 16,
    borderWidth: 2,
    borderColor: "transparent",
    overflow: "hidden",
  },
  toggleActive: {
    borderColor: "#4a90d9",
  },
  toggleIcon: {
    fontSize: 32,
    marginBottom: 4,
  },
  toggleLabel: {
    fontSize: 14,
    fontWeight: "600",
    color: "#ffffff",
  },
  contentArea: {
    flex: 1,
    paddingHorizontal: 16,
  },
  toastContainer: {
    position: "absolute",
    top: 60,
    left: 20,
    right: 20,
    zIndex: 100,
    padding: 12,
    borderRadius: 10,
    alignItems: "center",
  },
  toastSuccess: {
    backgroundColor: "rgba(74, 222, 128, 0.15)",
    borderWidth: 1,
    borderColor: "#4ade80",
  },
  toastError: {
    backgroundColor: "rgba(248, 113, 113, 0.15)",
    borderWidth: 1,
    borderColor: "#f87171",
  },
  toastText: {
    fontSize: 14,
    fontWeight: "500",
    color: "#ffffff",
  },
  voiceArea: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  timer: {
    fontSize: 48,
    fontWeight: "200",
    color: "#ffffff",
    marginBottom: 32,
    fontVariant: ["tabular-nums"],
  },
  recordContainer: {
    width: 100,
    height: 100,
    alignItems: "center",
    justifyContent: "center",
  },
  pulseRing: {
    position: "absolute",
    width: 100,
    height: 100,
    borderRadius: 50,
    borderWidth: 3,
    borderColor: "#ff3b30",
  },
  recordButton: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: "#4a4a6e",
    alignItems: "center",
    justifyContent: "center",
  },
  recordButtonActive: {
    backgroundColor: "#ff3b30",
  },
  recordPressed: {
    opacity: 0.7,
    transform: [{ scale: 0.95 }],
  },
  recordDisabled: {
    opacity: 0.4,
  },
  recordMicIcon: {
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: "#ffffff",
  },
  recordStopIcon: {
    width: 24,
    height: 24,
    borderRadius: 4,
    backgroundColor: "#ffffff",
  },
  voiceHint: {
    fontSize: 14,
    color: "#666",
    marginTop: 16,
  },
  textInputContainer: {
    backgroundColor: "#1a1a2e",
    borderRadius: 12,
    padding: 12,
    minHeight: 120,
    position: "relative",
  },
  textInput: {
    fontSize: 18,
    color: "#ffffff",
    paddingBottom: 40,
    minHeight: 80,
    textAlignVertical: "top",
  },
  sendButton: {
    position: "absolute",
    bottom: 10,
    right: 10,
    backgroundColor: "#4a90d9",
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
  },
  sendButtonText: {
    color: "#ffffff",
    fontSize: 15,
    fontWeight: "600",
  },
  processingArea: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  processingStageText: {
    fontSize: 16,
    color: "#999",
    marginTop: 12,
  },
  agentQuestionBubble: {
    backgroundColor: "#1a1a2e",
    borderRadius: 12,
    padding: 14,
    marginBottom: 12,
    borderLeftWidth: 3,
    borderLeftColor: "#4a90d9",
    alignSelf: "stretch",
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
  followUpRow: {
    flexDirection: "row",
    alignSelf: "stretch",
    marginBottom: 16,
    gap: 8,
  },
  followUpInput: {
    flex: 1,
    fontSize: 16,
    color: "#ffffff",
    padding: 12,
    backgroundColor: "#1a1a2e",
    borderRadius: 10,
    maxHeight: 80,
  },
  followUpSendButton: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: "#4a90d9",
    borderRadius: 10,
    justifyContent: "center",
  },
  sendPressed: {
    opacity: 0.7,
  },
  sendDisabled: {
    opacity: 0.4,
  },
  followUpSendText: {
    color: "#ffffff",
    fontSize: 15,
    fontWeight: "600",
  },
  sendTextDisabled: {
    color: "#999",
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
  followUpVoiceArea: {
    alignItems: "center",
    marginBottom: 16,
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
  followUpDuration: {
    color: "#999",
    fontSize: 13,
    textAlign: "center",
    marginTop: 4,
  },
});

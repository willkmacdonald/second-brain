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
  ScrollView,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import {
  useAudioRecorder,
  AudioModule,
  useAudioRecorderState,
  RecordingPresets,
} from "expo-audio";
import { useSpeechRecognitionEvent } from "expo-speech-recognition";
import * as Clipboard from "expo-clipboard";
import * as Haptics from "expo-haptics";
import {
  sendCapture,
  sendVoiceCapture,
  sendFollowUp,
  sendFollowUpVoice,
} from "../../lib/ag-ui-client";
import { reportError } from "../../lib/telemetry";
import { Sentry } from "../../lib/sentry";
import {
  checkOnDeviceSupport,
  requestSpeechPermissions,
  startOnDeviceRecognition,
  stopRecognition,
  abortRecognition,
} from "../../lib/speech";
import { API_BASE_URL, API_KEY, MAX_FOLLOW_UPS } from "../../constants/config";
import { theme, BucketName } from "../../constants/theme";

const BUCKETS: BucketName[] = ["People", "Projects", "Ideas", "Admin"];
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

  // On-device speech recognition state
  const [transcriptText, setTranscriptText] = useState("");
  const transcriptRef = useRef("");
  const [audioFileUri, setAudioFileUri] = useState<string | null>(null);
  const [useOnDevice, setUseOnDevice] = useState(false);
  const [speechPermissionGranted, setSpeechPermissionGranted] = useState(false);

  // Ref to track intentional stop (so "end" event knows to submit)
  const wasRecordingRef = useRef(false);
  // Ref to track if we are in follow-up mode when "end" fires
  const isFollowUpRecordingRef = useRef(false);
  // Ref to guard speech event handlers against cross-screen event leaks
  // (e.g. investigate screen's voice session firing events into capture screen)
  const isRecordingRef = useRef(false);

  useEffect(() => {
    isRecordingRef.current = isRecording;
  }, [isRecording]);

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

  // Trace ID state (for debugging -- displayed after capture)
  const [lastTraceId, setLastTraceId] = useState<string | null>(null);
  const [traceIdCopied, setTraceIdCopied] = useState(false);

  // Pulsing animation for recording indicator
  const pulseAnim = useRef(new Animated.Value(1)).current;
  const cleanupRef = useRef<(() => void) | null>(null);

  // Audio recorder (used only for cloud fallback path)
  const audioRecorder = useAudioRecorder(RecordingPresets.HIGH_QUALITY);
  const recorderState = useAudioRecorderState(audioRecorder, 100);

  // --- Speech recognition event hooks (must be at top level) ---

  // Real-time transcription results
  useSpeechRecognitionEvent("result", (event) => {
    const transcript = event.results[0]?.transcript ?? "";
    // Only update the submission ref if we got actual text -- stop() can
    // fire a final "result" with an empty transcript that would wipe out
    // the real transcription before the "end" event reads it.
    if (transcript) {
      transcriptRef.current = transcript;
    }
    setTranscriptText(transcript);
  });

  // Audio file URI for fallback (persisted audio from expo-speech-recognition)
  useSpeechRecognitionEvent("audiostart", (event) => {
    if (!isRecordingRef.current) return; // Ignore events from other screens
    setAudioFileUri(event.uri ?? null);
  });

  // Error during speech recognition -- fall back to cloud if audio file exists
  useSpeechRecognitionEvent("error", (event) => {
    if (!isRecordingRef.current) return; // Ignore events from other screens
    console.warn("Speech recognition error:", event.error, event.message);
    if (audioFileUri && API_KEY) {
      // Fall back to cloud upload with the persisted audio file
      setProcessing(true);
      setProcessingStage("uploading");
      const voiceFallback = sendVoiceCapture({
        audioUri: audioFileUri,
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
            console.error("Voice capture fallback error:", error);
            Sentry.captureMessage(
              `Voice capture fallback error: ${error}`,
              "error",
            );
            setProcessing(false);
            setProcessingStage(null);
            setToast({
              message: error || "Couldn\u2019t file your capture. Try again.",
              type: "error",
            });
          },
        },
      });
      setLastTraceId(voiceFallback.traceId);
      cleanupRef.current = voiceFallback.cleanup;
    }
    setIsRecording(false);
  });

  // Speech recognition ended -- submit transcribed text
  useSpeechRecognitionEvent("end", () => {
    if (!wasRecordingRef.current) return;
    wasRecordingRef.current = false;

    // Read from ref, not state -- avoids stale closure where "end" fires
    // before React re-renders with the latest "result" event's transcript.
    const text = transcriptRef.current.trim();

    // Check if this was a follow-up recording
    if (isFollowUpRecordingRef.current) {
      isFollowUpRecordingRef.current = false;
      if (!misunderstoodInboxItemId || !API_KEY) return;

      // Submit transcribed text as a text follow-up
      setIsReclassifying(true);
      const followUpResult = sendFollowUp({
        inboxItemId: misunderstoodInboxItemId,
        followUpText: text || "",
        followUpRound: followUpRound,
        apiKey: API_KEY,
        traceId: lastTraceId ?? undefined,
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
            if (followUpRound >= MAX_FOLLOW_UPS) {
              setIsReclassifying(false);
              setToast({
                message: "Couldn\u2019t classify. Check inbox later.",
                type: "error",
              });
              setTimeout(resetState, AUTO_RESET_MS);
              return;
            }
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
      cleanupRef.current = followUpResult.cleanup;
      return;
    }

    // Primary capture path -- submit transcribed text via sendCapture
    if (!API_KEY) {
      setToast({ message: "No API key configured", type: "error" });
      return;
    }

    // If no transcript was captured, don't submit -- the "end" event
    // sometimes fires without a final "result" (e.g., very short recordings
    // or recognition failing silently). Submitting empty text causes an
    // Azure API error.
    if (!text) {
      setToast({ message: "Nothing captured. Try again.", type: "error" });
      return;
    }

    setProcessing(true);
    setProcessingStage("classifying");

    const captureResult = sendCapture({
      message: text || "",
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
      captureSource: "voice",
    });
    setLastTraceId(captureResult.traceId);
    cleanupRef.current = captureResult.cleanup;
  });

  // --- Permission request: combined speech + mic when entering voice mode ---
  useEffect(() => {
    if (mode !== "voice") return;

    (async () => {
      const onDeviceSupported = await checkOnDeviceSupport();

      if (onDeviceSupported) {
        // Request speech recognition permissions (includes mic)
        const { granted } = await requestSpeechPermissions();
        if (granted) {
          setUseOnDevice(true);
          setSpeechPermissionGranted(true);
          setPermissionGranted(true);
          await AudioModule.setAudioModeAsync({
            allowsRecording: true,
            playsInSilentMode: true,
          });
        } else {
          // Speech recognition denied -- fall back to mic-only for cloud path
          setSpeechPermissionGranted(false);
          setUseOnDevice(false);
          const micStatus =
            await AudioModule.requestRecordingPermissionsAsync();
          if (micStatus.granted) {
            setPermissionGranted(true);
            await AudioModule.setAudioModeAsync({
              allowsRecording: true,
              playsInSilentMode: true,
            });
          } else {
            setPermissionGranted(false);
            showToast("Mic permission required");
          }
        }
      } else {
        // On-device not supported -- request mic permission only for cloud fallback
        setUseOnDevice(false);
        setSpeechPermissionGranted(false);
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

  // Cleanup SSE and speech recognition on unmount
  useEffect(() => {
    return () => {
      if (cleanupRef.current) {
        cleanupRef.current();
        cleanupRef.current = null;
      }
      abortRecognition();
    };
  }, []);

  const resetState = useCallback(() => {
    setProcessing(false);
    setProcessingStage(null);
    setThought("");
    setTranscriptText("");
    transcriptRef.current = "";
    setAudioFileUri(null);
    setHitlQuestion(null);
    setHitlThreadId(null);
    setHitlInboxItemId(null);
    setHitlTopBuckets([]);
    setFollowUpRound(0);
    setAgentQuestion(null);
    setMisunderstoodInboxItemId(null);
    setIsReclassifying(false);
    setFollowUpText("");
    setLastTraceId(null);
    setTraceIdCopied(false);
    setMode("voice");
  }, []);

  const handleRecordToggle = useCallback(async () => {
    if (!permissionGranted) {
      showToast("Mic permission required");
      return;
    }

    if (isRecording) {
      // Stop recording
      if (useOnDevice) {
        // On-device path: stop speech recognition, "end" event handles submission
        wasRecordingRef.current = true;
        stopRecognition();
        setIsRecording(false);
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
      } else {
        // Cloud fallback path: exact existing behavior
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

        const voiceResult = sendVoiceCapture({
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
              Sentry.captureMessage(
                `Voice capture error: ${error}`,
                "error",
              );
              setProcessing(false);
              setProcessingStage(null);
              setToast({
                message: error || "Couldn\u2019t file your capture. Try again.",
                type: "error",
              });
            },
          },
        });
        setLastTraceId(voiceResult.traceId);
        cleanupRef.current = voiceResult.cleanup;
      }
    } else {
      // Start recording
      if (useOnDevice) {
        // On-device path: start speech recognition (handles audio internally)
        setTranscriptText("");
        transcriptRef.current = "";
        setAudioFileUri(null);
        startOnDeviceRecognition();
        setIsRecording(true);
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);
      } else {
        // Cloud fallback path: exact existing behavior
        await audioRecorder.prepareToRecordAsync();
        audioRecorder.record();
        setIsRecording(true);
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);
      }
    }
  }, [
    isRecording,
    permissionGranted,
    useOnDevice,
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
    setLastTraceId(captureResult.traceId);
    cleanupRef.current = captureResult.cleanup;
  }, [thought, processing, resetState]);

  const handleFollowUpSubmit = useCallback(() => {
    if (!followUpText.trim() || isReclassifying || !misunderstoodInboxItemId)
      return;

    setIsReclassifying(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);

    const followUpResult = sendFollowUp({
      inboxItemId: misunderstoodInboxItemId,
      followUpText: followUpText.trim(),
      followUpRound: followUpRound,
      apiKey: API_KEY,
      traceId: lastTraceId ?? undefined,
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
          if (followUpRound >= MAX_FOLLOW_UPS) {
            setIsReclassifying(false);
            setToast({
              message: "Couldn\u2019t classify. Check inbox later.",
              type: "error",
            });
            setTimeout(resetState, AUTO_RESET_MS);
            return;
          }
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
    cleanupRef.current = followUpResult.cleanup;
  }, [
    followUpText,
    isReclassifying,
    misunderstoodInboxItemId,
    followUpRound,
    lastTraceId,
    resetState,
  ]);

  const handleVoiceFollowUp = useCallback(async () => {
    if (!misunderstoodInboxItemId || isReclassifying) return;

    if (useOnDevice) {
      // On-device path: stop speech recognition, "end" event handles submission
      wasRecordingRef.current = true;
      isFollowUpRecordingRef.current = true;
      stopRecognition();
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    } else {
      // Cloud fallback path: exact existing behavior
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

      const voiceFollowUpResult = sendFollowUpVoice({
        audioUri: uri,
        inboxItemId: misunderstoodInboxItemId,
        followUpRound: followUpRound,
        apiKey: API_KEY,
        traceId: lastTraceId ?? undefined,
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
            if (followUpRound >= MAX_FOLLOW_UPS) {
              setIsReclassifying(false);
              setToast({
                message: "Couldn\u2019t classify. Check inbox later.",
                type: "error",
              });
              setTimeout(resetState, AUTO_RESET_MS);
              return;
            }
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
      cleanupRef.current = voiceFollowUpResult.cleanup;
    }
  }, [
    misunderstoodInboxItemId,
    isReclassifying,
    useOnDevice,
    audioRecorder,
    recorderState.durationMillis,
    followUpRound,
    lastTraceId,
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
      if (useOnDevice) {
        // On-device path: start speech recognition for follow-up
        setTranscriptText("");
        transcriptRef.current = "";
        setAudioFileUri(null);
        startOnDeviceRecognition();
        setIsRecording(true);
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);
      } else {
        // Cloud fallback path: exact existing behavior
        await audioRecorder.prepareToRecordAsync();
        audioRecorder.record();
        setIsRecording(true);
        Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy);
      }
    }
  }, [
    isRecording,
    permissionGranted,
    useOnDevice,
    audioRecorder,
    handleVoiceFollowUp,
  ]);

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
          {/* Trace ID for debugging -- tap to copy full ID */}
          {lastTraceId && (
            <Pressable
              onPress={async () => {
                await Clipboard.setStringAsync(lastTraceId);
                setTraceIdCopied(true);
                setTimeout(() => setTraceIdCopied(false), 1500);
              }}
              style={styles.traceIdRow}
            >
              <Text style={styles.traceIdText}>
                trace: {lastTraceId.slice(0, 8)}...
              </Text>
              <Text style={styles.traceIdHint}>
                {traceIdCopied ? "Copied!" : "tap to copy"}
              </Text>
            </Pressable>
          )}
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
          <Text
            style={[
              styles.toggleLabel,
              mode === "voice" && { color: theme.colors.text },
            ]}
          >
            Voice
          </Text>
        </Pressable>
        <Pressable
          style={[
            styles.toggleButton,
            mode === "text" && styles.toggleActive,
          ]}
          onPress={() => setMode("text")}
        >
          <Text
            style={[
              styles.toggleLabel,
              mode === "text" && { color: theme.colors.text },
            ]}
          >
            Text
          </Text>
        </Pressable>
      </View>

      {/* Main content area */}
      <View style={styles.contentArea}>
        {/* Agent question bubble -- shown during HITL follow-up */}
        {agentQuestion && (
          <View style={styles.agentQuestionBubble}>
            <Text style={styles.agentQuestionText}>{agentQuestion}</Text>
            <Text style={styles.followUpHint}>
              Reply below (follow-up {followUpRound} of {MAX_FOLLOW_UPS})
            </Text>
          </View>
        )}

        {/* Processing stage indicator -- with transcribed text visible above for on-device path */}
        {processingStage && (
          <View style={styles.processingArea}>
            {/* Show transcribed text during classification for on-device voice captures */}
            {transcriptText.trim() && useOnDevice && (
              <ScrollView
                style={styles.transcriptProcessingScroll}
                contentContainerStyle={styles.transcriptProcessingContent}
              >
                <Text style={styles.transcriptProcessingText}>
                  {transcriptText}
                </Text>
              </ScrollView>
            )}
            <ActivityIndicator size="large" color={theme.colors.accent} />
            <Text style={styles.processingStageText}>
              {processingStage === "uploading"
                ? "Uploading..."
                : processingStage === "classifying"
                  ? "Classifying..."
                  : "Processing..."}
            </Text>
          </View>
        )}

        {/* Voice mode content (record button, timer/transcription) -- hidden during processing, HITL, and bucket picker */}
        {mode === "voice" && !processingStage && !agentQuestion && !hitlQuestion && (
          <View style={styles.voiceArea}>
            {/* On-device: show real-time transcription text during recording */}
            {isRecording && useOnDevice && (
              <ScrollView
                style={styles.transcriptScroll}
                contentContainerStyle={styles.transcriptContent}
              >
                <Text style={styles.transcriptText}>
                  {transcriptText || "Listening..."}
                </Text>
              </ScrollView>
            )}

            {/* Cloud fallback: show timer during recording */}
            {isRecording && !useOnDevice && (
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

        {/* Text mode content (text input + send button) -- hidden during processing and bucket picker */}
        {mode === "text" && !processingStage && !agentQuestion && !hitlQuestion && (
          <View style={styles.textInputContainer}>
            <TextInput
              style={styles.textInput}
              value={thought}
              onChangeText={setThought}
              placeholder="What's on your mind?"
              placeholderTextColor={theme.colors.textFaint}
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
            {/* On-device follow-up: show transcription text */}
            {isRecording && useOnDevice && (
              <Text style={styles.followUpTranscript}>
                {transcriptText || "Listening..."}
              </Text>
            )}
            {/* Cloud fallback follow-up: show timer */}
            {isRecording && !useOnDevice && (
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
              placeholderTextColor={theme.colors.textFaint}
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
                const bucketColors = theme.colors.buckets[bucket];
                return (
                  <Pressable
                    key={bucket}
                    onPress={() => handleBucketSelect(bucket)}
                    disabled={isResolving}
                    style={({ pressed }) => [
                      isTopBucket
                        ? {
                            ...styles.bucketButtonPrimary,
                            backgroundColor: bucketColors.bg,
                            borderColor: bucketColors.dot + "66",
                          }
                        : styles.bucketButtonSecondary,
                      pressed && styles.bucketPressed,
                      isResolving && styles.bucketDisabled,
                    ]}
                  >
                    <Text
                      style={
                        isTopBucket
                          ? {
                              ...styles.bucketTextPrimary,
                              color: bucketColors.fg,
                            }
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
    backgroundColor: theme.colors.bg,
  },
  toggleRow: {
    flexDirection: "row",
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 8,
    gap: 2,
    backgroundColor: theme.colors.surface,
    marginHorizontal: 16,
    borderRadius: 10,
    padding: 3,
  },
  toggleButton: {
    flex: 1,
    paddingVertical: 8,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: "transparent",
    borderRadius: 8,
    overflow: "hidden",
  },
  toggleActive: {
    backgroundColor: theme.colors.surfaceHi,
  },
  toggleLabel: {
    fontSize: 13,
    fontWeight: "600",
    color: theme.colors.textMuted,
    fontFamily: theme.fonts.bodySemiBold,
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
    backgroundColor: "rgba(125, 220, 160, 0.15)",
    borderWidth: 1,
    borderColor: theme.colors.ok,
  },
  toastError: {
    backgroundColor: "rgba(255, 107, 107, 0.15)",
    borderWidth: 1,
    borderColor: theme.colors.err,
  },
  toastText: {
    fontSize: 14,
    fontWeight: "500",
    color: theme.colors.text,
    fontFamily: theme.fonts.body,
  },
  traceIdRow: {
    flexDirection: "row",
    alignItems: "center",
    marginTop: 6,
    gap: 8,
  },
  traceIdText: {
    fontSize: 11,
    fontFamily: theme.fonts.mono,
    color: theme.colors.textDim,
  },
  traceIdHint: {
    fontSize: 10,
    color: theme.colors.textFaint,
  },
  voiceArea: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  timer: {
    fontSize: 48,
    fontWeight: "200",
    color: theme.colors.text,
    marginBottom: 32,
    fontVariant: ["tabular-nums"],
    fontFamily: theme.fonts.mono,
  },
  transcriptScroll: {
    maxHeight: 200,
    marginBottom: 24,
    alignSelf: "stretch",
  },
  transcriptContent: {
    paddingHorizontal: 8,
  },
  transcriptText: {
    fontFamily: theme.fonts.display,
    fontSize: 26,
    lineHeight: 34,
    letterSpacing: -0.4,
    fontWeight: "400",
    color: theme.colors.text,
  },
  transcriptProcessingScroll: {
    maxHeight: 160,
    marginBottom: 20,
    alignSelf: "stretch",
  },
  transcriptProcessingContent: {
    paddingHorizontal: 8,
  },
  transcriptProcessingText: {
    fontSize: 16,
    color: theme.colors.textDim,
    lineHeight: 24,
    textAlign: "center",
    fontFamily: theme.fonts.body,
  },
  followUpTranscript: {
    fontSize: 14,
    color: theme.colors.textDim,
    lineHeight: 20,
    textAlign: "center",
    marginBottom: 8,
    paddingHorizontal: 8,
    fontFamily: theme.fonts.display,
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
    borderColor: theme.colors.recording,
  },
  recordButton: {
    width: 86,
    height: 86,
    borderRadius: 43,
    backgroundColor: theme.colors.text,
    alignItems: "center",
    justifyContent: "center",
  },
  recordButtonActive: {
    width: 84,
    height: 84,
    borderRadius: 42,
    backgroundColor: theme.colors.recording,
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
    backgroundColor: theme.colors.bg,
  },
  recordStopIcon: {
    width: 24,
    height: 24,
    borderRadius: 5,
    backgroundColor: theme.colors.text,
  },
  voiceHint: {
    fontSize: 14,
    color: theme.colors.textFaint,
    marginTop: 16,
    fontFamily: theme.fonts.body,
  },
  textInputContainer: {
    backgroundColor: theme.colors.surface,
    borderRadius: 12,
    padding: 12,
    minHeight: 120,
    position: "relative",
  },
  textInput: {
    fontSize: 18,
    color: theme.colors.text,
    paddingBottom: 40,
    minHeight: 80,
    textAlignVertical: "top",
    fontFamily: theme.fonts.body,
  },
  sendButton: {
    position: "absolute",
    bottom: 10,
    right: 10,
    backgroundColor: theme.colors.accent,
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
  },
  sendButtonText: {
    color: theme.colors.text,
    fontSize: 15,
    fontWeight: "600",
    fontFamily: theme.fonts.bodySemiBold,
  },
  processingArea: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  processingStageText: {
    fontSize: 16,
    color: theme.colors.textDim,
    marginTop: 12,
    fontFamily: theme.fonts.body,
  },
  agentQuestionBubble: {
    backgroundColor: theme.colors.accentDim,
    borderRadius: 14,
    padding: 14,
    marginBottom: 12,
    borderLeftWidth: 2,
    borderLeftColor: theme.colors.accent,
    alignSelf: "stretch",
  },
  agentQuestionText: {
    fontSize: 15,
    color: theme.colors.text,
    lineHeight: 22,
    fontFamily: theme.fonts.body,
  },
  followUpHint: {
    fontSize: 11,
    color: theme.colors.textFaint,
    marginTop: 6,
    fontFamily: theme.fonts.mono,
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
    color: theme.colors.text,
    padding: 12,
    backgroundColor: theme.colors.surface,
    borderRadius: 10,
    maxHeight: 80,
    fontFamily: theme.fonts.body,
  },
  followUpSendButton: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: theme.colors.accent,
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
    color: theme.colors.text,
    fontSize: 15,
    fontWeight: "600",
    fontFamily: theme.fonts.bodySemiBold,
  },
  sendTextDisabled: {
    color: theme.colors.textDim,
  },
  hitlContainer: {
    marginTop: 12,
  },
  hitlQuestion: {
    fontSize: 14,
    color: theme.colors.textDim,
    lineHeight: 20,
    marginBottom: 12,
    textAlign: "center",
    fontFamily: theme.fonts.body,
  },
  bucketRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 8,
  },
  bucketButtonPrimary: {
    flex: 1,
    paddingVertical: 10,
    paddingHorizontal: 4,
    borderRadius: 12,
    alignItems: "center",
    borderWidth: StyleSheet.hairlineWidth,
  },
  bucketButtonSecondary: {
    flex: 1,
    backgroundColor: "transparent",
    paddingVertical: 10,
    paddingHorizontal: 4,
    borderRadius: 12,
    alignItems: "center",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: theme.colors.hairline,
    opacity: 0.5,
  },
  bucketPressed: {
    opacity: 0.7,
  },
  bucketDisabled: {
    opacity: 0.4,
  },
  bucketTextPrimary: {
    fontSize: 13,
    fontFamily: theme.fonts.bodySemiBold,
  },
  bucketTextSecondary: {
    fontSize: 13,
    fontFamily: theme.fonts.bodyMedium,
    color: theme.colors.textMuted,
  },
  resolvingText: {
    fontSize: 12,
    color: theme.colors.accent,
    textAlign: "center",
    marginTop: 8,
    fontFamily: theme.fonts.body,
  },
  followUpVoiceArea: {
    alignItems: "center",
    marginBottom: 16,
  },
  followUpRecordButton: {
    width: 60,
    height: 60,
    borderRadius: 30,
    backgroundColor: theme.colors.surface,
    alignItems: "center",
    justifyContent: "center",
    alignSelf: "center",
    marginTop: 12,
  },
  followUpRecordButtonActive: {
    backgroundColor: theme.colors.recording,
  },
  followUpDuration: {
    color: theme.colors.textDim,
    fontSize: 13,
    textAlign: "center",
    marginTop: 4,
    fontFamily: theme.fonts.mono,
  },
});

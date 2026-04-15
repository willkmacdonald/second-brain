import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { Stack, useLocalSearchParams } from "expo-router";
import { useSpeechRecognitionEvent } from "expo-speech-recognition";
import { InvestigateBubble } from "../components/InvestigateBubble";
import { QuickActionChips } from "../components/QuickActionChips";
import { API_KEY } from "../constants/config";
import { sendInvestigation } from "../lib/investigate-client";
import {
  abortRecognition,
  requestSpeechPermissions,
  startOnDeviceRecognition,
  stopRecognition,
} from "../lib/speech";

interface ChatMessage {
  id: string;
  role: "user" | "agent";
  content: string;
  isStreaming: boolean;
}

/**
 * Investigation chat screen.
 *
 * Provides a conversational interface to the investigation agent with:
 * - Streaming SSE responses with markdown rendering
 * - Quick action chips for common queries (shown when chat is empty)
 * - Voice input via on-device speech recognition
 * - Follow-up questions within the same thread
 * - "New chat" header icon to reset conversation
 * - Optional initialQuery route param for deep-link auto-send
 */
export default function InvestigateScreen() {
  const { initialQuery } = useLocalSearchParams<{
    initialQuery?: string;
  }>();

  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState("");
  const [threadId, setThreadId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isRecording, setIsRecording] = useState(false);

  const cleanupRef = useRef<(() => void) | null>(null);
  const transcriptRef = useRef("");
  const wasRecordingRef = useRef(false);
  const initialQuerySentRef = useRef(false);

  // --- Speech recognition hooks (must be at top level -- Pitfall 5) ---

  useSpeechRecognitionEvent("result", (event) => {
    const transcript = event.results[0]?.transcript ?? "";
    // Guard against empty transcript from stop() firing empty result
    // (MEMORY.md: expo-speech-recognition stop() fires empty result event)
    if (transcript) {
      transcriptRef.current = transcript;
    }
    setInputText(transcript || transcriptRef.current);
  });

  useSpeechRecognitionEvent("end", () => {
    if (!wasRecordingRef.current) return;
    wasRecordingRef.current = false;
    setIsRecording(false);

    // Read from ref to avoid stale closure
    const text = transcriptRef.current.trim();
    if (text) {
      // Auto-submit the transcribed text
      handleSendWithText(text);
    }
  });

  // --- Send logic ---

  const handleSendWithText = useCallback(
    (text: string) => {
      if (!text.trim() || isLoading || !API_KEY) return;

      const ts = Date.now();
      const userMsg: ChatMessage = {
        id: `user-${ts}`,
        role: "user",
        content: text.trim(),
        isStreaming: false,
      };

      const agentMsgId = `agent-${ts}`;
      const agentMsg: ChatMessage = {
        id: agentMsgId,
        role: "agent",
        content: "",
        isStreaming: true,
      };

      setMessages((prev) => [...prev, userMsg, agentMsg]);
      setInputText("");
      transcriptRef.current = "";
      setIsLoading(true);

      const { cleanup } = sendInvestigation({
        question: text.trim(),
        threadId: threadId ?? undefined,
        apiKey: API_KEY,
        callbacks: {
          onThinking: () => {
            // No-op: agent bubble already shows "Thinking..." when
            // content is empty and isStreaming is true
          },
          onText: (content: string) => {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === agentMsgId
                  ? { ...msg, content: msg.content + content }
                  : msg,
              ),
            );
          },
          onDone: (newThreadId: string) => {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === agentMsgId ? { ...msg, isStreaming: false } : msg,
              ),
            );
            setThreadId(newThreadId);
            setIsLoading(false);
          },
          onError: (message: string) => {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === agentMsgId
                  ? { ...msg, content: message, isStreaming: false }
                  : msg,
              ),
            );
            setIsLoading(false);
          },
        },
      });

      cleanupRef.current = cleanup;
    },
    [isLoading, threadId],
  );

  const handleSend = useCallback(() => {
    // If recording, stop it and prevent the end event from double-submitting
    if (isRecording) {
      wasRecordingRef.current = false;
      stopRecognition();
      setIsRecording(false);
    }
    handleSendWithText(inputText);
  }, [inputText, handleSendWithText, isRecording]);

  // --- Quick action chip handler ---

  const handleChipSelect = useCallback(
    (query: string) => {
      handleSendWithText(query);
    },
    [handleSendWithText],
  );

  // --- Voice input ---

  const handleVoicePress = useCallback(async () => {
    if (isRecording) {
      stopRecognition();
      setIsRecording(false);
    } else {
      const { granted } = await requestSpeechPermissions();
      if (!granted) return;
      transcriptRef.current = "";
      wasRecordingRef.current = true;
      startOnDeviceRecognition();
      setIsRecording(true);
    }
  }, [isRecording]);

  // --- New chat ---

  const handleNewChat = useCallback(() => {
    cleanupRef.current?.();
    cleanupRef.current = null;
    setMessages([]);
    setThreadId(null);
    setInputText("");
    setIsLoading(false);
    transcriptRef.current = "";
  }, []);

  // --- Auto-send initialQuery on mount ---

  useEffect(() => {
    if (initialQuery && !initialQuerySentRef.current) {
      initialQuerySentRef.current = true;
      // Small delay to ensure component is fully mounted
      const timer = setTimeout(() => {
        handleSendWithText(initialQuery);
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [initialQuery, handleSendWithText]);

  // --- Cleanup on unmount ---

  useEffect(() => {
    return () => {
      cleanupRef.current?.();
      abortRecognition();
    };
  }, []);

  // --- Render ---

  const renderMessage = useCallback(
    ({ item }: { item: ChatMessage }) => (
      <InvestigateBubble
        role={item.role}
        content={item.content}
        isStreaming={item.isStreaming}
      />
    ),
    [],
  );

  const renderEmpty = useCallback(
    () => (
      <View style={styles.emptyInner}>
        <QuickActionChips onSelect={handleChipSelect} />
      </View>
    ),
    [handleChipSelect],
  );

  const canSend = inputText.trim().length > 0 && !isLoading;

  return (
    <>
      <Stack.Screen
        options={{
          headerShown: true,
          headerTitle: "Investigate",
          headerStyle: { backgroundColor: "#0f0f23" },
          headerTintColor: "#ffffff",
          headerRight: () => (
            <Pressable onPress={handleNewChat} style={styles.headerButton}>
              <Text style={styles.headerButtonText}>New</Text>
            </Pressable>
          ),
        }}
      />
      <KeyboardAvoidingView
        style={styles.container}
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        keyboardVerticalOffset={90}
      >
        <FlatList
          data={[...messages].reverse()}
          renderItem={renderMessage}
          keyExtractor={(item) => item.id}
          inverted
          ListEmptyComponent={renderEmpty}
          contentContainerStyle={
            messages.length === 0 ? styles.emptyContainer : styles.listContent
          }
          keyboardShouldPersistTaps="handled"
        />
        <View style={styles.inputBar}>
          <TextInput
            style={styles.textInput}
            placeholder="Ask about your system..."
            placeholderTextColor="#666666"
            value={inputText}
            onChangeText={setInputText}
            onSubmitEditing={handleSend}
            returnKeyType="send"
            multiline={false}
            editable={!isLoading}
          />
          <Pressable
            onPress={handleVoicePress}
            style={[
              styles.iconButton,
              isRecording && styles.iconButtonRecording,
            ]}
          >
            <Text style={styles.iconText}>{isRecording ? "\u23F9" : "\uD83C\uDF99"}</Text>
          </Pressable>
          <Pressable
            onPress={handleSend}
            style={[
              styles.iconButton,
              canSend ? styles.iconButtonEnabled : styles.iconButtonDisabled,
            ]}
            disabled={!canSend}
          >
            <Text style={styles.iconText}>{"\u2191"}</Text>
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0f0f23",
  },
  listContent: {
    paddingVertical: 8,
  },
  emptyContainer: {
    flexGrow: 1,
    justifyContent: "center",
  },
  emptyInner: {
    transform: [{ scaleY: -1 }],
  },
  inputBar: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#1a1a2e",
    borderTopColor: "#333333",
    borderTopWidth: 1,
    padding: 8,
    gap: 8,
  },
  textInput: {
    flex: 1,
    backgroundColor: "#0f0f23",
    color: "#ffffff",
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 10,
    fontSize: 16,
  },
  iconButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: "center",
    justifyContent: "center",
  },
  iconButtonEnabled: {
    backgroundColor: "#4a90d9",
  },
  iconButtonDisabled: {
    backgroundColor: "#333333",
  },
  iconButtonRecording: {
    backgroundColor: "#ff4444",
  },
  iconText: {
    color: "#ffffff",
    fontSize: 18,
  },
  headerButton: {
    marginRight: 8,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
    backgroundColor: "#1a1a2e",
  },
  headerButtonText: {
    color: "#4a90d9",
    fontSize: 14,
    fontWeight: "600",
  },
});

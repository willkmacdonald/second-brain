import { useState } from "react";
import {
  Modal,
  SafeAreaView,
  View,
  Text,
  TextInput,
  Pressable,
  StyleSheet,
} from "react-native";
import { useApiKey } from "../contexts/ApiKeyContext";
import { theme } from "../constants/theme";

/**
 * Full-screen modal that appears on first launch when no API key is stored.
 * Blocks app interaction until the user enters their key.
 * In dev builds where EXPO_PUBLIC_API_KEY env var is set, this never appears.
 */
export function ApiKeyGate() {
  const { apiKey, setApiKey, isLoading } = useApiKey();
  const [inputValue, setInputValue] = useState("");

  const handleContinue = async () => {
    const trimmed = inputValue.trim();
    if (!trimmed) return;
    await setApiKey(trimmed);
  };

  return (
    <Modal visible={!apiKey && !isLoading} animationType="fade">
      <SafeAreaView style={styles.container}>
        <View style={styles.content}>
          <Text style={styles.title}>Second Brain</Text>
          <Text style={styles.subtitle}>
            Enter your API key to get started
          </Text>

          <Text style={styles.label}>API KEY</Text>
          <TextInput
            style={styles.input}
            secureTextEntry
            autoFocus
            placeholder="Paste your API key"
            placeholderTextColor={theme.colors.textMuted}
            value={inputValue}
            onChangeText={setInputValue}
            autoCapitalize="none"
            autoCorrect={false}
          />

          <Pressable
            style={[
              styles.button,
              !inputValue.trim() && styles.buttonDisabled,
            ]}
            onPress={handleContinue}
            disabled={!inputValue.trim()}
          >
            <Text style={styles.buttonText}>Continue</Text>
          </Pressable>

          <Text style={styles.hint}>
            You can change this later in Settings
          </Text>
        </View>
      </SafeAreaView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.bg,
  },
  content: {
    flex: 1,
    justifyContent: "center",
    paddingHorizontal: 24,
  },
  title: {
    fontSize: 28,
    fontWeight: "400",
    fontFamily: theme.fonts.display,
    fontStyle: "italic",
    color: theme.colors.text,
    textAlign: "center",
  },
  subtitle: {
    fontSize: 15,
    fontFamily: theme.fonts.body,
    color: theme.colors.textMuted,
    textAlign: "center",
    marginTop: 8,
    marginBottom: 32,
  },
  label: {
    fontSize: 11,
    fontWeight: "600",
    fontFamily: theme.fonts.bodySemiBold,
    color: theme.colors.textMuted,
    textTransform: "uppercase",
    letterSpacing: 1.4,
    marginBottom: 4,
  },
  input: {
    backgroundColor: theme.colors.surfaceHi,
    borderRadius: 10,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: theme.colors.hairline,
    padding: 14,
    color: theme.colors.text,
    fontSize: 15,
    fontFamily: theme.fonts.body,
  },
  button: {
    backgroundColor: theme.colors.accent,
    borderRadius: 10,
    paddingVertical: 14,
    marginTop: 16,
    alignItems: "center",
  },
  buttonDisabled: {
    opacity: 0.4,
  },
  buttonText: {
    color: theme.colors.text,
    fontSize: 16,
    fontWeight: "600",
    fontFamily: theme.fonts.bodySemiBold,
  },
  hint: {
    fontSize: 12,
    fontFamily: theme.fonts.body,
    color: theme.colors.textDim,
    textAlign: "center",
    marginTop: 12,
  },
});

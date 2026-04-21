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
            placeholderTextColor="#666"
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
    backgroundColor: "#0f0f23",
  },
  content: {
    flex: 1,
    justifyContent: "center",
    paddingHorizontal: 24,
  },
  title: {
    fontSize: 28,
    fontWeight: "bold",
    color: "#fff",
    textAlign: "center",
  },
  subtitle: {
    fontSize: 15,
    color: "#888",
    textAlign: "center",
    marginTop: 8,
    marginBottom: 32,
  },
  label: {
    fontSize: 11,
    fontWeight: "600",
    color: "#888",
    textTransform: "uppercase",
    marginBottom: 4,
  },
  input: {
    backgroundColor: "#1a1a2e",
    borderRadius: 10,
    padding: 14,
    color: "#fff",
    fontSize: 15,
  },
  button: {
    backgroundColor: "#4a90d9",
    borderRadius: 10,
    paddingVertical: 14,
    marginTop: 16,
    alignItems: "center",
  },
  buttonDisabled: {
    opacity: 0.4,
  },
  buttonText: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "600",
  },
  hint: {
    fontSize: 12,
    color: "#666",
    textAlign: "center",
    marginTop: 12,
  },
});

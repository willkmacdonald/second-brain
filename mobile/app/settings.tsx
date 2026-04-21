import { useState } from "react";
import {
  SafeAreaView,
  ScrollView,
  View,
  Text,
  TextInput,
  Pressable,
  Platform,
  StyleSheet,
} from "react-native";
import { Stack } from "expo-router";
import { useApiKey } from "../contexts/ApiKeyContext";
import { API_BASE_URL } from "../constants/config";

/**
 * Settings screen with API key display/editing and app info.
 * Pushed from Status screen gear icon or root navigation.
 */
export default function SettingsScreen() {
  const { apiKey, setApiKey } = useApiKey();
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState("");
  const [showToast, setShowToast] = useState(false);

  const maskedKey = (() => {
    if (!apiKey) return "Not set";
    if (apiKey.length < 10) return "****";
    return `${apiKey.slice(0, 3)}...${apiKey.slice(-4)}`;
  })();

  const handleChange = () => {
    setEditValue("");
    setIsEditing(true);
  };

  const handleCancel = () => {
    setIsEditing(false);
    setEditValue("");
  };

  const handleSave = async () => {
    const trimmed = editValue.trim();
    if (!trimmed) return;
    await setApiKey(trimmed);
    setIsEditing(false);
    setEditValue("");
    setShowToast(true);
    setTimeout(() => setShowToast(false), 2000);
  };

  return (
    <SafeAreaView style={styles.container}>
      <Stack.Screen
        options={{
          headerShown: true,
          headerTitle: "Settings",
          headerStyle: { backgroundColor: "#0f0f23" },
          headerTintColor: "#ffffff",
        }}
      />

      <ScrollView style={styles.scroll}>
        {/* API Configuration Section */}
        <Text style={styles.sectionTitle}>API Configuration</Text>

        <Text style={styles.label}>API KEY</Text>
        {!isEditing ? (
          <View style={styles.displayRow}>
            <Text style={styles.maskedKey}>{maskedKey}</Text>
            <Pressable onPress={handleChange}>
              <Text style={styles.changeButton}>Change</Text>
            </Pressable>
          </View>
        ) : (
          <View>
            <TextInput
              style={styles.input}
              secureTextEntry
              placeholder="Enter API key"
              placeholderTextColor="#666"
              value={editValue}
              onChangeText={setEditValue}
              autoCapitalize="none"
              autoCorrect={false}
              autoFocus
            />
            <View style={styles.buttonRow}>
              <Pressable style={styles.cancelButton} onPress={handleCancel}>
                <Text style={styles.cancelText}>Cancel</Text>
              </Pressable>
              <Pressable style={styles.saveButton} onPress={handleSave}>
                <Text style={styles.saveText}>Save</Text>
              </Pressable>
            </View>
          </View>
        )}

        {/* About Section */}
        <Text style={[styles.sectionTitle, { marginTop: 32 }]}>About</Text>

        <View style={styles.aboutRow}>
          <Text style={styles.aboutLabel}>Version</Text>
          <Text style={styles.aboutValue}>1.0.0</Text>
        </View>
        <View style={styles.aboutRow}>
          <Text style={styles.aboutLabel}>API</Text>
          <Text style={styles.aboutValue} numberOfLines={1}>
            {API_BASE_URL}
          </Text>
        </View>
      </ScrollView>

      {/* Success Toast */}
      {showToast && (
        <View style={styles.toast}>
          <Text style={styles.toastText}>API key saved</Text>
        </View>
      )}
    </SafeAreaView>
  );
}

const monoFont = Platform.select({ ios: "Menlo", android: "monospace" });

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0f0f23",
  },
  scroll: {
    paddingHorizontal: 16,
    paddingTop: 16,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: "600",
    color: "#fff",
    marginBottom: 12,
  },
  label: {
    fontSize: 11,
    fontWeight: "600",
    color: "#888",
    textTransform: "uppercase",
    marginBottom: 4,
  },
  displayRow: {
    backgroundColor: "#1a1a2e",
    borderRadius: 10,
    padding: 14,
    marginTop: 4,
    flexDirection: "row",
    alignItems: "center",
  },
  maskedKey: {
    fontSize: 15,
    color: "#ccc",
    flex: 1,
    fontFamily: monoFont,
  },
  changeButton: {
    color: "#4a90d9",
    fontSize: 14,
    fontWeight: "600",
  },
  input: {
    backgroundColor: "#1a1a2e",
    borderRadius: 10,
    padding: 14,
    color: "#fff",
    fontSize: 15,
    marginTop: 4,
  },
  buttonRow: {
    flexDirection: "row",
    gap: 8,
    marginTop: 8,
  },
  cancelButton: {
    backgroundColor: "#2a2a4e",
    borderRadius: 8,
    paddingVertical: 10,
    paddingHorizontal: 16,
  },
  cancelText: {
    color: "#ccc",
    fontSize: 14,
    fontWeight: "600",
  },
  saveButton: {
    backgroundColor: "#4a90d9",
    borderRadius: 8,
    paddingVertical: 10,
    paddingHorizontal: 16,
  },
  saveText: {
    color: "#fff",
    fontSize: 14,
    fontWeight: "600",
  },
  aboutRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: "#1a1a2e",
    borderRadius: 10,
    padding: 14,
    marginBottom: 8,
  },
  aboutLabel: {
    fontSize: 14,
    color: "#888",
  },
  aboutValue: {
    fontSize: 14,
    color: "#ccc",
    flex: 1,
    textAlign: "right",
    marginLeft: 16,
  },
  toast: {
    position: "absolute",
    bottom: 100,
    left: 32,
    right: 32,
    backgroundColor: "rgba(74, 222, 128, 0.15)",
    borderColor: "#4ade80",
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    alignItems: "center",
  },
  toastText: {
    color: "#4ade80",
    fontSize: 14,
    fontWeight: "600",
  },
});

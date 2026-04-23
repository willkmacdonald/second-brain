import { useState } from "react";
import {
  SafeAreaView,
  ScrollView,
  View,
  Text,
  TextInput,
  Pressable,
  StyleSheet,
} from "react-native";
import { Stack } from "expo-router";
import { ChevronRight } from "lucide-react-native";

import { useApiKey } from "../contexts/ApiKeyContext";
import { API_BASE_URL } from "../constants/config";
import { theme } from "../constants/theme";
import { CapsLabel } from "../components/CapsLabel";

/**
 * Settings screen with API key display/editing and app info.
 * Pushed from Status screen gear icon or root navigation.
 *
 * Grouped iOS-style card layout per D-13 design spec.
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
          headerTitle: "",
          headerStyle: { backgroundColor: theme.colors.bg },
          headerTintColor: theme.colors.text,
          headerShadowVisible: false,
        }}
      />

      <ScrollView style={styles.scroll}>
        {/* Settings heading */}
        <Text style={styles.heading}>Settings</Text>

        {/* Account section */}
        <View style={styles.sectionWrapper}>
          <View style={styles.sectionLabelContainer}>
            <CapsLabel>Account</CapsLabel>
          </View>
          <View style={styles.sectionCard}>
            {!isEditing ? (
              <>
                <Pressable style={styles.row} onPress={handleChange}>
                  <Text style={styles.rowTitle}>API key</Text>
                  <Text style={styles.rowValue}>{maskedKey}</Text>
                  <ChevronRight size={11} color={theme.colors.textFaint} strokeWidth={1.8} />
                </Pressable>
                <View style={styles.rowSeparator} />
                <View style={styles.row}>
                  <Text style={styles.rowTitle}>Signed in as</Text>
                  <Text style={styles.rowValue}>will</Text>
                  <ChevronRight size={11} color={theme.colors.textFaint} strokeWidth={1.8} />
                </View>
              </>
            ) : (
              <View style={styles.editContainer}>
                <TextInput
                  style={styles.input}
                  secureTextEntry
                  placeholder="Enter API key"
                  placeholderTextColor={theme.colors.textMuted}
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
          </View>
        </View>

        {/* About section */}
        <View style={[styles.sectionWrapper, { marginTop: 18 }]}>
          <View style={styles.sectionLabelContainer}>
            <CapsLabel>About</CapsLabel>
          </View>
          <View style={styles.sectionCard}>
            <View style={styles.row}>
              <Text style={styles.rowTitle}>Version</Text>
              <Text style={styles.rowValue}>1.0.0</Text>
              <ChevronRight size={11} color={theme.colors.textFaint} strokeWidth={1.8} />
            </View>
            <View style={styles.rowSeparator} />
            <View style={styles.row}>
              <Text style={styles.rowTitle}>API</Text>
              <Text style={styles.rowValue} numberOfLines={1}>
                {API_BASE_URL}
              </Text>
              <ChevronRight size={11} color={theme.colors.textFaint} strokeWidth={1.8} />
            </View>
          </View>
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

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: theme.colors.bg,
  },
  scroll: {
    paddingTop: 4,
  },
  heading: {
    fontFamily: theme.fonts.display,
    fontSize: 36,
    fontWeight: "400",
    fontStyle: "italic",
    letterSpacing: -0.8,
    color: theme.colors.text,
    paddingHorizontal: 20,
    paddingBottom: 14,
  },
  sectionWrapper: {
    marginTop: 0,
  },
  sectionLabelContainer: {
    paddingHorizontal: 20,
    paddingBottom: 6,
  },
  sectionCard: {
    marginHorizontal: 16,
    backgroundColor: theme.colors.surface,
    borderRadius: 14,
    overflow: "hidden",
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: theme.colors.hairline,
  },
  row: {
    paddingVertical: 13,
    paddingHorizontal: 14,
    flexDirection: "row",
    alignItems: "center",
  },
  rowSeparator: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: theme.colors.hairline,
    marginLeft: 14,
  },
  rowTitle: {
    flex: 1,
    fontSize: 14,
    color: theme.colors.text,
    letterSpacing: -0.15,
    fontFamily: theme.fonts.body,
  },
  rowValue: {
    fontSize: 13,
    color: theme.colors.textDim,
    marginRight: 8,
    fontFamily: theme.fonts.mono,
  },
  editContainer: {
    padding: 14,
  },
  input: {
    backgroundColor: theme.colors.surfaceHi,
    borderRadius: 10,
    padding: 14,
    color: theme.colors.text,
    fontSize: 15,
    fontFamily: theme.fonts.body,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: theme.colors.hairline,
  },
  buttonRow: {
    flexDirection: "row",
    gap: 8,
    marginTop: 8,
  },
  cancelButton: {
    backgroundColor: theme.colors.surfaceHi,
    borderRadius: 8,
    paddingVertical: 10,
    paddingHorizontal: 16,
  },
  cancelText: {
    color: theme.colors.textDim,
    fontSize: 14,
    fontWeight: "600",
    fontFamily: theme.fonts.body,
  },
  saveButton: {
    backgroundColor: theme.colors.accent,
    borderRadius: 8,
    paddingVertical: 10,
    paddingHorizontal: 16,
  },
  saveText: {
    color: theme.colors.bg,
    fontSize: 14,
    fontWeight: "600",
    fontFamily: theme.fonts.body,
  },
  toast: {
    position: "absolute",
    bottom: 100,
    left: 32,
    right: 32,
    backgroundColor: theme.colors.ok + "22",
    borderColor: theme.colors.ok,
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    alignItems: "center",
  },
  toastText: {
    color: theme.colors.ok,
    fontSize: 14,
    fontWeight: "600",
    fontFamily: theme.fonts.body,
  },
});

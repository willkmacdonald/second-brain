import { View, StyleSheet, Alert, Platform, ToastAndroid } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { router } from "expo-router";
import { CaptureButton } from "../../components/CaptureButton";

function showComingSoon() {
  if (Platform.OS === "android") {
    ToastAndroid.show("Coming soon", ToastAndroid.SHORT);
  } else {
    Alert.alert("Coming soon");
  }
}

export default function CaptureScreen() {
  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.buttonStack}>
        <CaptureButton
          label="Voice"
          icon={"\uD83C\uDF99\uFE0F"}
          onPress={showComingSoon}
          disabled
        />
        <CaptureButton
          label="Text"
          icon={"\u270D\uFE0F"}
          onPress={() => router.push("/capture/text")}
        />
        <CaptureButton
          label="Photo"
          icon={"\uD83D\uDCF7"}
          onPress={showComingSoon}
          disabled
        />
        <CaptureButton
          label="Video"
          icon={"\uD83C\uDFA5"}
          onPress={showComingSoon}
          disabled
        />
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#0f0f23",
  },
  buttonStack: {
    flex: 1,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
});

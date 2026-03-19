import { ExpoSpeechRecognitionModule } from "expo-speech-recognition";

/**
 * Check whether the device supports on-device speech recognition.
 *
 * This is the gate for deciding on-device vs cloud fallback. If false,
 * the app silently falls back to the existing cloud upload -> Whisper flow.
 */
export async function checkOnDeviceSupport(): Promise<boolean> {
  return ExpoSpeechRecognitionModule.supportsOnDeviceRecognition();
}

/**
 * Request both microphone and speech recognition permissions.
 *
 * iOS requires TWO separate permissions: microphone access AND speech
 * recognition. If microphone permission is denied, speech recognition
 * permission is not requested.
 */
export async function requestSpeechPermissions(): Promise<{ granted: boolean }> {
  const mic =
    await ExpoSpeechRecognitionModule.requestMicrophonePermissionsAsync();
  if (!mic.granted) return { granted: false };
  const speech =
    await ExpoSpeechRecognitionModule.requestSpeechRecognizerPermissionsAsync();
  return { granted: speech.granted };
}

/**
 * Start on-device speech recognition with streaming interim results.
 *
 * Configuration:
 * - continuous: true -- keeps recognizing until explicitly stopped
 * - interimResults: true -- provides real-time word-by-word feedback
 * - requiresOnDeviceRecognition: true -- forces on-device, no network
 * - addsPunctuation: true -- automatic punctuation insertion
 * - recordingOptions.persist: true -- saves audio file for fallback if
 *   transcription fails mid-recording
 */
export function startOnDeviceRecognition(): void {
  ExpoSpeechRecognitionModule.start({
    lang: "en-US",
    interimResults: true,
    continuous: true,
    requiresOnDeviceRecognition: true,
    addsPunctuation: true,
    recordingOptions: {
      persist: true,
    },
  });
}

/**
 * Stop speech recognition gracefully. Fires a final result event with
 * the complete transcription before stopping.
 */
export function stopRecognition(): void {
  ExpoSpeechRecognitionModule.stop();
}

/**
 * Abort speech recognition immediately. Discards any pending results.
 * Use for cleanup on component unmount.
 */
export function abortRecognition(): void {
  ExpoSpeechRecognitionModule.abort();
}

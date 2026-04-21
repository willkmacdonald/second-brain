export const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8003";
// Live binding: changes via setRuntimeApiKey() propagate to all importers
export let API_KEY = process.env.EXPO_PUBLIC_API_KEY ?? "";
export const USER_ID = "will"; // Single-user system per PROJECT.md
export const MAX_FOLLOW_UPS = 2;

/**
 * Update the API key at runtime (called by ApiKeyProvider after SecureStore read).
 * Uses ES module live binding -- all modules importing API_KEY see the new value.
 */
export function setRuntimeApiKey(key: string) {
  API_KEY = key;
}

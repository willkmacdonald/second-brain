import * as SecureStore from "expo-secure-store";
import {
  createContext,
  useContext,
  useState,
  useEffect,
  ReactNode,
} from "react";
import { setRuntimeApiKey } from "../constants/config";

interface ApiKeyContextType {
  apiKey: string;
  setApiKey: (key: string) => Promise<void>;
  isLoading: boolean;
}

const ApiKeyContext = createContext<ApiKeyContextType>({
  apiKey: "",
  setApiKey: async () => {},
  isLoading: true,
});

export function ApiKeyProvider({ children }: { children: ReactNode }) {
  const [apiKey, setApiKeyState] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const envKey = process.env.EXPO_PUBLIC_API_KEY;
    if (envKey) {
      setApiKeyState(envKey);
      setRuntimeApiKey(envKey);
      setIsLoading(false);
      return;
    }
    SecureStore.getItemAsync("api_key").then((stored) => {
      const key = stored ?? "";
      setApiKeyState(key);
      setRuntimeApiKey(key);
      setIsLoading(false);
    });
  }, []);

  const setApiKey = async (key: string) => {
    await SecureStore.setItemAsync("api_key", key);
    setApiKeyState(key);
    setRuntimeApiKey(key);
  };

  return (
    <ApiKeyContext.Provider value={{ apiKey, setApiKey, isLoading }}>
      {children}
    </ApiKeyContext.Provider>
  );
}

export const useApiKey = () => useContext(ApiKeyContext);

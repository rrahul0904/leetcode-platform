import {
  focusManager,
  onlineManager,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import * as Network from "expo-network";
import { type ReactNode, useEffect, useState } from "react";
import { AppState, type AppStateStatus, Platform } from "react-native";

function onlineFromState(state: Network.NetworkState): boolean {
  if (state.isInternetReachable === false) return false;
  return state.isConnected !== false;
}

export function MobileQueryProvider({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 15_000,
            gcTime: 10 * 60_000,
            retry: (failureCount, error) => {
              const status =
                error && typeof error === "object" && "status" in error
                  ? Number(error.status)
                  : undefined;
              if (status === 401 || status === 403 || status === 404) return false;
              return failureCount < 2;
            },
            refetchOnReconnect: true,
          },
          mutations: {
            retry: false,
          },
        },
      }),
  );

  useEffect(() => {
    if (Platform.OS === "web") return;
    const onAppStateChange = (status: AppStateStatus) => {
      focusManager.setFocused(status === "active");
    };
    const subscription = AppState.addEventListener("change", onAppStateChange);
    focusManager.setFocused(AppState.currentState === "active");
    return () => subscription.remove();
  }, []);

  useEffect(() => {
    let cancelled = false;
    void Network.getNetworkStateAsync().then((state) => {
      if (!cancelled) onlineManager.setOnline(onlineFromState(state));
    });
    const subscription = Network.addNetworkStateListener((state) => {
      onlineManager.setOnline(onlineFromState(state));
    });
    return () => {
      cancelled = true;
      subscription.remove();
    };
  }, []);

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

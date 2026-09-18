import { createApiClient } from "@rigor/api-client/client";

import { secureTokenStore } from "../auth/token-store";
import { mobileConfig } from "../config";

let unauthorizedHandler: (() => void | Promise<void>) | undefined;

export function setUnauthorizedHandler(handler?: () => void | Promise<void>) {
  unauthorizedHandler = handler;
}

export const apiClient = createApiClient({
  baseUrl: mobileConfig.apiUrl,
  getAccessToken: async () => (await secureTokenStore.get())?.accessToken ?? null,
  onUnauthorized: async () => {
    await secureTokenStore.clear();
    await unauthorizedHandler?.();
  },
  defaultHeaders: {
    "X-Rigor-Client": "mobile",
  },
});

import * as SecureStore from "expo-secure-store";

export interface StoredTokens {
  accessToken: string;
  refreshToken?: string;
  expiresAt?: number;
}

export interface TokenStore {
  get(): Promise<StoredTokens | null>;
  set(tokens: StoredTokens): Promise<void>;
  clear(): Promise<void>;
}

const TOKEN_KEY = "rigor.auth.tokens.v1";

function parseTokens(value: string | null): StoredTokens | null {
  if (!value) return null;
  try {
    const parsed = JSON.parse(value) as unknown;
    if (!parsed || typeof parsed !== "object") return null;
    const candidate = parsed as Record<string, unknown>;
    if (typeof candidate.accessToken !== "string" || candidate.accessToken.length === 0) {
      return null;
    }
    return {
      accessToken: candidate.accessToken,
      ...(typeof candidate.refreshToken === "string"
        ? { refreshToken: candidate.refreshToken }
        : {}),
      ...(typeof candidate.expiresAt === "number" ? { expiresAt: candidate.expiresAt } : {}),
    };
  } catch {
    return null;
  }
}

export const secureTokenStore: TokenStore = {
  async get() {
    return parseTokens(await SecureStore.getItemAsync(TOKEN_KEY));
  },

  async set(tokens) {
    await SecureStore.setItemAsync(TOKEN_KEY, JSON.stringify(tokens));
  },

  async clear() {
    await SecureStore.deleteItemAsync(TOKEN_KEY);
  },
};

export function createMemoryTokenStore(initial: StoredTokens | null = null): TokenStore {
  let value = initial;
  return {
    async get() {
      return value;
    },
    async set(tokens) {
      value = tokens;
    },
    async clear() {
      value = null;
    },
  };
}

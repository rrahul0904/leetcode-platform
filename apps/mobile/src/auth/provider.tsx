import * as AuthSession from "expo-auth-session";
import * as WebBrowser from "expo-web-browser";
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { getPrincipal } from "../api/candidate";
import { setUnauthorizedHandler } from "../api/client";
import type { AuthenticatedPrincipal } from "../api/types";
import { mobileConfig } from "../config";
import { secureTokenStore, type StoredTokens } from "./token-store";

WebBrowser.maybeCompleteAuthSession();

type AuthStatus = "restoring" | "anonymous" | "authenticating" | "authenticated";

interface AuthContextValue {
  status: AuthStatus;
  principal: AuthenticatedPrincipal | null;
  error: string | null;
  signIn(identity?: string): Promise<void>;
  signOut(): Promise<void>;
}

interface TokenEndpointPayload {
  access_token?: unknown;
  refresh_token?: unknown;
  expires_in?: unknown;
}

const AuthContext = createContext<AuthContextValue | null>(null);
const redirectUri = AuthSession.makeRedirectUri({ scheme: "rigor", path: "auth/callback" });

function tokenEndpointBody(
  code: string,
  verifier: string,
  refreshToken?: string,
): Record<string, string> {
  if (refreshToken) {
    return {
      grant_type: "refresh_token",
      refresh_token: refreshToken,
      client_id: mobileConfig.oidcClientId,
    };
  }
  return {
    grant_type: "authorization_code",
    code,
    client_id: mobileConfig.oidcClientId,
    redirect_uri: redirectUri,
    code_verifier: verifier,
  };
}

async function exchangeTokens(
  tokenEndpoint: string,
  body: Record<string, string>,
): Promise<StoredTokens> {
  const localProvider = tokenEndpoint.includes("/local-oidc/token");
  const response = await fetch(tokenEndpoint, {
    method: "POST",
    headers: {
      "Content-Type": localProvider
        ? "application/json"
        : "application/x-www-form-urlencoded",
      Accept: "application/json",
    },
    body: localProvider ? JSON.stringify(body) : new URLSearchParams(body).toString(),
  });
  if (!response.ok) {
    throw new Error(`OIDC token exchange returned ${response.status}.`);
  }
  const payload = (await response.json()) as TokenEndpointPayload;
  if (typeof payload.access_token !== "string" || payload.access_token.length === 0) {
    throw new Error("OIDC token response did not include an access token.");
  }
  const expiresIn =
    typeof payload.expires_in === "number" && Number.isFinite(payload.expires_in)
      ? payload.expires_in
      : undefined;
  return {
    accessToken: payload.access_token,
    ...(typeof payload.refresh_token === "string"
      ? { refreshToken: payload.refresh_token }
      : {}),
    ...(expiresIn ? { expiresAt: Date.now() + expiresIn * 1000 } : {}),
  };
}

async function refreshTokens(tokens: StoredTokens): Promise<StoredTokens | null> {
  if (!tokens.refreshToken) return null;
  const discovery = await AuthSession.fetchDiscoveryAsync(mobileConfig.oidcIssuer);
  if (!discovery.tokenEndpoint) return null;
  return exchangeTokens(
    discovery.tokenEndpoint,
    tokenEndpointBody("", "", tokens.refreshToken),
  );
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("restoring");
  const [principal, setPrincipal] = useState<AuthenticatedPrincipal | null>(null);
  const [error, setError] = useState<string | null>(null);

  const invalidate = useCallback(async () => {
    await secureTokenStore.clear();
    setPrincipal(null);
    setStatus("anonymous");
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(invalidate);
    return () => setUnauthorizedHandler(undefined);
  }, [invalidate]);

  useEffect(() => {
    let cancelled = false;
    async function restore() {
      try {
        let tokens = await secureTokenStore.get();
        if (!tokens) {
          if (!cancelled) setStatus("anonymous");
          return;
        }
        if (tokens.expiresAt && tokens.expiresAt <= Date.now() + 30_000) {
          tokens = await refreshTokens(tokens);
          if (!tokens) {
            await secureTokenStore.clear();
            if (!cancelled) setStatus("anonymous");
            return;
          }
          await secureTokenStore.set(tokens);
        }
        const restored = await getPrincipal();
        if (!restored.roles.includes("candidate")) {
          throw new Error("The native application currently supports candidate accounts only.");
        }
        if (!cancelled) {
          setPrincipal(restored);
          setStatus("authenticated");
        }
      } catch (cause) {
        await secureTokenStore.clear();
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : "Session restoration failed.");
          setPrincipal(null);
          setStatus("anonymous");
        }
      }
    }
    void restore();
    return () => {
      cancelled = true;
    };
  }, []);

  const signIn = useCallback(async (identity = "candidate") => {
    setStatus("authenticating");
    setError(null);
    try {
      const discovery = await AuthSession.fetchDiscoveryAsync(mobileConfig.oidcIssuer);
      if (!discovery.authorizationEndpoint || !discovery.tokenEndpoint) {
        throw new Error("OIDC discovery is missing authorization or token endpoints.");
      }
      const request = new AuthSession.AuthRequest({
        clientId: mobileConfig.oidcClientId,
        redirectUri,
        responseType: AuthSession.ResponseType.Code,
        scopes: ["openid", "email", "profile"],
        usePKCE: true,
        extraParams: discovery.authorizationEndpoint.includes("/local-oidc/authorize")
          ? { identity }
          : {},
      });
      const response = await request.promptAsync(discovery);
      if (response.type !== "success") {
        setStatus("anonymous");
        return;
      }
      const code = response.params.code;
      if (!code || !request.codeVerifier) {
        throw new Error("OIDC authorization did not return a valid code/PKCE verifier.");
      }
      const tokens = await exchangeTokens(
        discovery.tokenEndpoint,
        tokenEndpointBody(code, request.codeVerifier),
      );
      await secureTokenStore.set(tokens);
      const authenticated = await getPrincipal();
      if (!authenticated.roles.includes("candidate")) {
        await secureTokenStore.clear();
        throw new Error("The native application currently supports candidate accounts only.");
      }
      setPrincipal(authenticated);
      setStatus("authenticated");
    } catch (cause) {
      await secureTokenStore.clear();
      setPrincipal(null);
      setError(cause instanceof Error ? cause.message : "Sign-in failed.");
      setStatus("anonymous");
    }
  }, []);

  const signOut = useCallback(async () => {
    await invalidate();
    setError(null);
  }, [invalidate]);

  const value = useMemo<AuthContextValue>(
    () => ({ status, principal, error, signIn, signOut }),
    [error, principal, signIn, signOut, status],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider.");
  return value;
}

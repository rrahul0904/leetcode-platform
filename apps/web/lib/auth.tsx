"use client";

import type { components } from "@rigor/api-client/schema";
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

export type Principal = components["schemas"]["AuthenticatedPrincipal"];
type TokenResponse = components["schemas"]["OIDCTokenResponse"];
type AuthStatus = "restoring" | "anonymous" | "authenticated";

type AuthContextValue = {
  status: AuthStatus;
  principal: Principal | null;
  signIn: (identity?: string, returnTo?: string) => Promise<void>;
  completeSignIn: (code: string, state: string) => Promise<void>;
  signOut: () => void;
};

const accessTokenKey = "rigor.auth.access-token";
const verifierKey = "rigor.auth.pkce-verifier";
const stateKey = "rigor.auth.state";
const nonceKey = "rigor.auth.nonce";
const returnToKey = "rigor.auth.return-to";
export const apiUrl =
  process.env.NEXT_PUBLIC_RIGOR_API_URL ?? "http://localhost:8002";
const authMode = process.env.NEXT_PUBLIC_RIGOR_AUTH_MODE ?? "local";
const clientId = process.env.NEXT_PUBLIC_RIGOR_OIDC_CLIENT_ID ?? "rigor-web";
const redirectUri =
  process.env.NEXT_PUBLIC_RIGOR_OIDC_REDIRECT_URI ??
  "http://localhost:3001/auth/callback";
const authorizationUrl =
  process.env.NEXT_PUBLIC_RIGOR_OIDC_AUTHORIZATION_URL ??
  `${apiUrl}/local-oidc/authorize`;
const tokenUrl =
  process.env.NEXT_PUBLIC_RIGOR_OIDC_TOKEN_URL ?? `${apiUrl}/local-oidc/token`;

const AuthContext = createContext<AuthContextValue | null>(null);

function base64url(value: Uint8Array) {
  return btoa(String.fromCharCode(...value))
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replaceAll("=", "");
}

function randomValue(byteLength = 32) {
  const bytes = new Uint8Array(byteLength);
  window.crypto.getRandomValues(bytes);
  return base64url(bytes);
}

export function storedAccessToken() {
  if (
    typeof window === "undefined" ||
    typeof window.localStorage === "undefined"
  )
    return null;
  return window.localStorage.getItem(accessTokenKey);
}

async function loadPrincipal(token: string): Promise<Principal> {
  const response = await fetch(`${apiUrl}/api/v1/auth/me`, {
    headers: { Accept: "application/json", Authorization: `Bearer ${token}` },
  });
  if (!response.ok)
    throw new Error(`Session validation returned ${response.status}`);
  return (await response.json()) as Principal;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("restoring");
  const [principal, setPrincipal] = useState<Principal | null>(null);

  useEffect(() => {
    const token = storedAccessToken();
    if (!token) {
      queueMicrotask(() => setStatus("anonymous"));
      return;
    }
    void loadPrincipal(token)
      .then((restored) => {
        setPrincipal(restored);
        setStatus("authenticated");
      })
      .catch(() => {
        window.localStorage.removeItem(accessTokenKey);
        setPrincipal(null);
        setStatus("anonymous");
      });
  }, []);

  useEffect(() => {
    const invalidate = () => {
      window.localStorage.removeItem(accessTokenKey);
      setPrincipal(null);
      setStatus("anonymous");
    };
    window.addEventListener("rigor:unauthorized", invalidate);
    return () => window.removeEventListener("rigor:unauthorized", invalidate);
  }, []);

  const signIn = useCallback(async (identity?: string, returnTo = "/") => {
    const verifier = randomValue(48);
    const challengeBytes = new Uint8Array(
      await window.crypto.subtle.digest(
        "SHA-256",
        new TextEncoder().encode(verifier),
      ),
    );
    const state = randomValue();
    const nonce = randomValue();
    window.sessionStorage.setItem(verifierKey, verifier);
    window.sessionStorage.setItem(stateKey, state);
    window.sessionStorage.setItem(nonceKey, nonce);
    window.sessionStorage.setItem(
      returnToKey,
      returnTo.startsWith("/") && !returnTo.startsWith("//") ? returnTo : "/",
    );
    const parameters = new URLSearchParams({
      client_id: clientId,
      redirect_uri: redirectUri,
      response_type: "code",
      scope: "openid email profile",
      state,
      nonce,
      code_challenge: base64url(challengeBytes),
      code_challenge_method: "S256",
    });
    if (authMode === "local" && identity) parameters.set("identity", identity);
    window.location.assign(`${authorizationUrl}?${parameters.toString()}`);
  }, []);

  const completeSignIn = useCallback(async (code: string, state: string) => {
    const expectedState = window.sessionStorage.getItem(stateKey);
    const verifier = window.sessionStorage.getItem(verifierKey);
    if (!expectedState || !verifier || state !== expectedState)
      throw new Error("The OIDC state or PKCE verifier is invalid.");
    const body = {
      grant_type: "authorization_code",
      code,
      client_id: clientId,
      redirect_uri: redirectUri,
      code_verifier: verifier,
    };
    const response = await fetch(tokenUrl, {
      method: "POST",
      headers: {
        "Content-Type":
          authMode === "local"
            ? "application/json"
            : "application/x-www-form-urlencoded",
      },
      body:
        authMode === "local" ? JSON.stringify(body) : new URLSearchParams(body),
    });
    if (!response.ok)
      throw new Error(`OIDC token exchange returned ${response.status}`);
    const tokens = (await response.json()) as TokenResponse;
    window.localStorage.setItem(accessTokenKey, tokens.access_token);
    window.sessionStorage.removeItem(verifierKey);
    window.sessionStorage.removeItem(stateKey);
    window.sessionStorage.removeItem(nonceKey);
    const restored = await loadPrincipal(tokens.access_token);
    setPrincipal(restored);
    setStatus("authenticated");
  }, []);

  const signOut = useCallback(() => {
    window.localStorage.removeItem(accessTokenKey);
    setPrincipal(null);
    setStatus("anonymous");
  }, []);

  const value = useMemo(
    () => ({ status, principal, signIn, completeSignIn, signOut }),
    [completeSignIn, principal, signIn, signOut, status],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}

export function authReturnPath() {
  const value = window.sessionStorage.getItem(returnToKey) ?? "/";
  window.sessionStorage.removeItem(returnToKey);
  return value.startsWith("/") && !value.startsWith("//") ? value : "/";
}

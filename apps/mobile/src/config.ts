import { z } from "zod";

const rawConfig = {
  apiUrl: process.env.EXPO_PUBLIC_API_URL,
  oidcIssuer: process.env.EXPO_PUBLIC_OIDC_ISSUER,
  oidcClientId: process.env.EXPO_PUBLIC_OIDC_CLIENT_ID,
  appOrigin: process.env.EXPO_PUBLIC_APP_ORIGIN,
};

const schema = z.object({
  apiUrl: z.url(),
  oidcIssuer: z.url(),
  oidcClientId: z.string().min(3),
  appOrigin: z.url().optional(),
});

const developmentDefaults = {
  apiUrl: "http://127.0.0.1:8002",
  oidcIssuer: "http://127.0.0.1:8002/local-oidc",
  oidcClientId: "rigor-mobile-local",
};

const candidate = {
  apiUrl: rawConfig.apiUrl ?? (__DEV__ ? developmentDefaults.apiUrl : undefined),
  oidcIssuer:
    rawConfig.oidcIssuer ?? (__DEV__ ? developmentDefaults.oidcIssuer : undefined),
  oidcClientId:
    rawConfig.oidcClientId ?? (__DEV__ ? developmentDefaults.oidcClientId : undefined),
  ...(rawConfig.appOrigin ? { appOrigin: rawConfig.appOrigin } : {}),
};

const parsed = schema.safeParse(candidate);
if (!parsed.success) {
  throw new Error(
    "Rigor mobile configuration is invalid. Set EXPO_PUBLIC_API_URL, EXPO_PUBLIC_OIDC_ISSUER, and EXPO_PUBLIC_OIDC_CLIENT_ID.",
  );
}

export const mobileConfig = parsed.data;

export interface ApiClientConfiguration {
  baseUrl: string;
  getAccessToken?: () => Promise<string | null>;
  fetchImplementation?: typeof fetch;
  defaultHeaders?: Readonly<Record<string, string>>;
  onUnauthorized?: () => void | Promise<void>;
}

export interface ApiRequestOptions extends Omit<RequestInit, "headers" | "signal"> {
  headers?: Readonly<Record<string, string>>;
  requireAuthentication?: boolean;
  signal?: AbortSignal | null | undefined;
}

export class ApiClientError extends Error {
  readonly status: number;
  readonly code: string | undefined;
  readonly details: unknown | undefined;

  constructor(message: string, status: number, code?: string, details?: unknown) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

// Compatibility alias retained for native clients that imported the original name.
export { ApiClientError as ApiError };

export interface ApiClient {
  request<T>(path: string, options?: ApiRequestOptions): Promise<T>;
}

function normalizeBaseUrl(baseUrl: string): string {
  const trimmed = baseUrl.trim().replace(/\/+$/, "");
  if (!trimmed) {
    throw new Error("API base URL is required.");
  }
  return trimmed;
}

async function readError(response: Response): Promise<ApiClientError> {
  const contentType = response.headers.get("content-type") ?? "";
  let details: unknown;

  try {
    details = contentType.includes("application/json")
      ? await response.json()
      : await response.text();
  } catch {
    details = undefined;
  }

  const record =
    details && typeof details === "object"
      ? (details as Record<string, unknown>)
      : undefined;
  const message =
    (typeof record?.detail === "string" && record.detail) ||
    (typeof record?.message === "string" && record.message) ||
    `API request failed with status ${response.status}.`;
  const code = typeof record?.code === "string" ? record.code : undefined;

  return new ApiClientError(message, response.status, code, details);
}

export function createApiClient(configuration: ApiClientConfiguration): ApiClient {
  const baseUrl = normalizeBaseUrl(configuration.baseUrl);
  const fetchImplementation = configuration.fetchImplementation ?? globalThis.fetch;

  if (!fetchImplementation) {
    throw new Error("A fetch implementation is required in this runtime.");
  }

  return {
    async request<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
      const token = configuration.getAccessToken
        ? await configuration.getAccessToken()
        : null;
      const headers = new Headers(configuration.defaultHeaders);
      const {
        headers: _requestHeaders,
        requireAuthentication,
        signal,
        ...requestInit
      } = options;

      for (const [name, value] of Object.entries(options.headers ?? {})) {
        headers.set(name, value);
      }

      if (!headers.has("accept")) {
        headers.set("accept", "application/json");
      }
      if (options.body && !headers.has("content-type")) {
        headers.set("content-type", "application/json");
      }
      if (token) {
        headers.set("authorization", `Bearer ${token}`);
      } else if (requireAuthentication) {
        await configuration.onUnauthorized?.();
        throw new ApiClientError("Authentication is required.", 401, "AUTH_REQUIRED");
      }

      const init: RequestInit = { ...requestInit, headers };
      if (signal !== undefined) {
        init.signal = signal;
      }
      const response = await fetchImplementation(
        `${baseUrl}/${path.replace(/^\/+/, "")}`,
        init,
      );

      if (!response.ok) {
        if (response.status === 401) {
          await configuration.onUnauthorized?.();
        }
        throw await readError(response);
      }
      if (response.status === 204) {
        return undefined as T;
      }

      const contentType = response.headers.get("content-type") ?? "";
      if (!contentType.includes("application/json")) {
        return (await response.text()) as T;
      }
      return (await response.json()) as T;
    },
  };
}

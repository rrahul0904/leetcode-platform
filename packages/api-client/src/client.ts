export interface ApiClientConfiguration {
  baseUrl: string;
  getAccessToken?: () => Promise<string | null>;
  fetchImplementation?: typeof fetch;
  defaultHeaders?: Readonly<Record<string, string>>;
}

export interface ApiRequestOptions extends Omit<RequestInit, "headers"> {
  headers?: Readonly<Record<string, string>>;
  requireAuthentication?: boolean;
}

export class ApiClientError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly details?: unknown;

  constructor(message: string, status: number, code?: string, details?: unknown) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

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
      } else if (options.requireAuthentication) {
        throw new ApiClientError("Authentication is required.", 401, "AUTH_REQUIRED");
      }

      const response = await fetchImplementation(
        `${baseUrl}/${path.replace(/^\/+/, "")}`,
        { ...options, headers },
      );

      if (!response.ok) {
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

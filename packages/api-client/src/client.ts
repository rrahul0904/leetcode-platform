export interface ApiClientConfiguration {
  baseUrl: string;
  getAccessToken?: () => Promise<string | null>;
  fetchImplementation?: typeof fetch;
  onUnauthorized?: () => void | Promise<void>;
  defaultHeaders?: Record<string, string>;
}

export interface ApiRequestOptions {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
  idempotencyKey?: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly correlationId?: string;
  readonly retryable?: boolean;

  constructor(
    status: number,
    message: string,
    details: {
      code?: string;
      correlationId?: string;
      retryable?: boolean;
    } = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = details.code;
    this.correlationId = details.correlationId;
    this.retryable = details.retryable;
  }
}

export interface ApiClient {
  request<T>(path: string, options?: ApiRequestOptions): Promise<T>;
}

interface ErrorPayload {
  code?: unknown;
  message?: unknown;
  correlation_id?: unknown;
  retryable?: unknown;
}

function normalizeBaseUrl(value: string): string {
  return value.endsWith("/") ? value.slice(0, -1) : value;
}

function stringValue(value: unknown): string | undefined {
  return typeof value === "string" ? value : undefined;
}

function booleanValue(value: unknown): boolean | undefined {
  return typeof value === "boolean" ? value : undefined;
}

async function parseError(response: Response): Promise<ApiError> {
  let payload: ErrorPayload = {};
  try {
    const body = (await response.json()) as unknown;
    if (body && typeof body === "object") {
      payload = body as ErrorPayload;
    }
  } catch {
    // Some infrastructure failures intentionally return an empty/non-JSON body.
  }

  return new ApiError(
    response.status,
    stringValue(payload.message) ?? `Rigor API returned ${response.status}`,
    {
      ...(stringValue(payload.code) ? { code: stringValue(payload.code) } : {}),
      ...(stringValue(payload.correlation_id)
        ? { correlationId: stringValue(payload.correlation_id) }
        : {}),
      ...(booleanValue(payload.retryable) !== undefined
        ? { retryable: booleanValue(payload.retryable) }
        : {}),
    },
  );
}

export function createApiClient(configuration: ApiClientConfiguration): ApiClient {
  const baseUrl = normalizeBaseUrl(configuration.baseUrl);
  const fetchImplementation = configuration.fetchImplementation ?? globalThis.fetch;

  if (!fetchImplementation) {
    throw new Error("A fetch implementation is required to create the Rigor API client.");
  }

  return {
    async request<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
      const accessToken = configuration.getAccessToken
        ? await configuration.getAccessToken()
        : null;
      const response = await fetchImplementation(`${baseUrl}${path}`, {
        method: options.method ?? "GET",
        headers: {
          Accept: "application/json",
          ...configuration.defaultHeaders,
          ...(options.body !== undefined ? { "Content-Type": "application/json" } : {}),
          ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
          ...(options.idempotencyKey
            ? { "Idempotency-Key": options.idempotencyKey }
            : {}),
          ...options.headers,
        },
        ...(options.body !== undefined ? { body: JSON.stringify(options.body) } : {}),
        ...(options.signal ? { signal: options.signal } : {}),
      });

      if (!response.ok) {
        if (response.status === 401 && configuration.onUnauthorized) {
          await configuration.onUnauthorized();
        }
        throw await parseError(response);
      }

      if (response.status === 204) {
        return undefined as T;
      }

      return (await response.json()) as T;
    },
  };
}

export type AuthMode = "protected" | "session";

export type ApiOptions = Omit<RequestInit, "credentials"> & {
  authMode?: AuthMode;
};

export interface ApiResponse<T> {
  data: T;
  status: number;
  headers: Headers;
}

interface ErrorEnvelope {
  error?: {
    code?: string;
    message?: string;
    request_id?: string;
  };
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId?: string;

  constructor(status: number, code: string, message: string, requestId?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

export interface ApiClientDependencies {
  fetch?: typeof globalThis.fetch;
  getAccessToken: () => string | null;
  refresh: () => Promise<void>;
  onAuthFailure: () => void;
}

export interface ApiClient {
  request<T>(path: string, options?: ApiOptions): Promise<ApiResponse<T>>;
}

const SESSION_PATHS = new Set([
  "/api/v1/auth/login",
  "/api/v1/auth/register",
  "/api/v1/auth/logout",
  "/api/v1/auth/refresh",
]);

function pathname(path: string) {
  return path.split("?", 1)[0];
}

async function apiErrorFrom(response: Response) {
  let body: ErrorEnvelope = {};
  try {
    body = (await response.json()) as ErrorEnvelope;
  } catch {
    // Non-JSON upstream failures still become a safe, typed API error.
  }

  return new ApiError(
    response.status,
    body.error?.code ?? "request_failed",
    body.error?.message ?? "The request could not be completed.",
    body.error?.request_id,
  );
}

async function apiResponse<T>(response: Response): Promise<ApiResponse<T>> {
  if (!response.ok) throw await apiErrorFrom(response);

  const data = response.status === 204 ? undefined : await response.json();
  return {
    data: data as T,
    status: response.status,
    headers: response.headers,
  };
}

export function createApiClient(dependencies: ApiClientDependencies): ApiClient {
  const fetchRequest = dependencies.fetch ?? globalThis.fetch;
  let refreshInFlight: Promise<void> | null = null;

  async function refreshOnce() {
    if (!refreshInFlight) {
      refreshInFlight = dependencies.refresh().finally(() => {
        refreshInFlight = null;
      });
    }
    return refreshInFlight;
  }

  async function request<T>(path: string, options: ApiOptions = {}): Promise<ApiResponse<T>> {
    if (!path.startsWith("/api/v1/")) {
      throw new Error("API requests must use a relative /api/v1/ path.");
    }

    const { authMode: requestedAuthMode, ...init } = options;
    const authMode = SESSION_PATHS.has(pathname(path))
      ? "session"
      : requestedAuthMode ?? "protected";

    async function send() {
      const headers = new Headers(init.headers);
      const accessToken = dependencies.getAccessToken();
      if (authMode === "protected" && accessToken) {
        headers.set("Authorization", `Bearer ${accessToken}`);
      }
      if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
        headers.set("Content-Type", "application/json");
      }
      const response = await fetchRequest(path, { ...init, headers, credentials: "include" });
      return { response, accessToken };
    }

    let { response, accessToken: requestAccessToken } = await send();
    if (response.status !== 401 || authMode === "session") {
      return apiResponse<T>(response);
    }

    if (dependencies.getAccessToken() === requestAccessToken) {
      try {
        await refreshOnce();
      } catch {
        dependencies.onAuthFailure();
        throw await apiErrorFrom(response);
      }
    }

    ({ response } = await send());
    if (response.status === 401) dependencies.onAuthFailure();
    return apiResponse<T>(response);
  }

  return { request };
}

let configuredClient: ApiClient = createApiClient({
  getAccessToken: () => null,
  refresh: () => Promise.reject(new Error("Auth provider is not mounted.")),
  onAuthFailure: () => undefined,
});

export function configureApiClient(client: ApiClient) {
  configuredClient = client;
  return () => {
    if (configuredClient === client) {
      configuredClient = createApiClient({
        getAccessToken: () => null,
        refresh: () => Promise.reject(new Error("Auth provider is not mounted.")),
        onAuthFailure: () => undefined,
      });
    }
  };
}

export function apiRequest<T>(path: string, options?: ApiOptions) {
  return configuredClient.request<T>(path, options);
}

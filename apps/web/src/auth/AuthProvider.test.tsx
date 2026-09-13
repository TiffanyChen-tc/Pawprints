import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "../App";
import { ApiError, apiRequest, createApiClient } from "../api/client";
import { AuthProvider } from "./AuthProvider";

const user = {
  id: "4f6d5325-6845-4c8a-ae11-2cfedb71ea45",
  email: "sam@example.com",
  display_name: "Sam",
};

const session = {
  access_token: "runtime-access-token",
  token_type: "Bearer",
  expires_in: 900,
  user,
};

function response(status: number, body?: unknown) {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
  });
}

function authError(status: number, code: string, message: string) {
  return response(status, {
    error: { code, message, request_id: "request-123" },
  });
}

function renderApp(path = "/") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
}

function requestPath(input: RequestInfo | URL) {
  return typeof input === "string" ? input : input instanceof URL ? input.pathname : input.url;
}

beforeEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  window.localStorage.clear();
  window.sessionStorage.clear();
});

describe("API client authentication recovery", () => {
  it("shares one refresh across concurrent 401 responses and retries each request once", async () => {
    let token = "expired-token";
    const refresh = vi.fn(async () => {
      await Promise.resolve();
      token = "renewed-token";
    });
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      const authorization = new Headers(init?.headers).get("Authorization");
      return authorization === "Bearer renewed-token"
        ? response(200, { ok: true })
        : authError(401, "not_authenticated", "Authentication is required.");
    });
    const client = createApiClient({
      fetch: fetchMock,
      getAccessToken: () => token,
      refresh,
      onAuthFailure: vi.fn(),
    });

    const results = await Promise.all([
      client.request<{ ok: boolean }>("/api/v1/events/timeline?date=2026-09-09"),
      client.request<{ ok: boolean }>("/api/v1/categories"),
    ]);

    expect(results.map(({ data }) => data)).toEqual([{ ok: true }, { ok: true }]);
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(fetchMock.mock.calls.every(([, init]) => init?.credentials === "include")).toBe(true);
  });

  it("does not rotate refresh again when a stale request returns 401 after renewal", async () => {
    let token = "expired-token";
    let releaseDelayed401: ((value: Response) => void) | undefined;
    let markRefreshComplete: (() => void) | undefined;
    const delayed401 = new Promise<Response>((resolve) => {
      releaseDelayed401 = resolve;
    });
    const refreshComplete = new Promise<void>((resolve) => {
      markRefreshComplete = resolve;
    });
    const refresh = vi.fn(async () => {
      token = "renewed-token";
      markRefreshComplete?.();
    });
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = requestPath(input);
      const authorization = new Headers(init?.headers).get("Authorization");
      if (authorization === "Bearer renewed-token") return response(200, { path });
      if (path === "/api/v1/categories") return delayed401;
      return authError(401, "not_authenticated", "Authentication is required.");
    });
    const client = createApiClient({
      fetch: fetchMock,
      getAccessToken: () => token,
      refresh,
      onAuthFailure: vi.fn(),
    });

    const requests = Promise.all([
      client.request<{ path: string }>("/api/v1/events/timeline?date=2026-09-09"),
      client.request<{ path: string }>("/api/v1/categories"),
    ]);
    await refreshComplete;
    releaseDelayed401?.(authError(401, "not_authenticated", "Authentication is required."));

    const results = await requests;
    expect(results.map(({ data }) => data.path)).toEqual([
      "/api/v1/events/timeline?date=2026-09-09",
      "/api/v1/categories",
    ]);
    expect(refresh).toHaveBeenCalledTimes(1);
    const categoryCalls = fetchMock.mock.calls.filter(
      ([input]) => requestPath(input) === "/api/v1/categories",
    );
    expect(categoryCalls).toHaveLength(2);
    expect(new Headers(categoryCalls[1]?.[1]?.headers).get("Authorization")).toBe(
      "Bearer renewed-token",
    );
  });

  it("stops after one retry when a protected request remains unauthorized", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      authError(401, "not_authenticated", "Authentication is required."),
    );
    const refresh = vi.fn().mockResolvedValue(undefined);
    const client = createApiClient({
      fetch: fetchMock,
      getAccessToken: () => "access-token",
      refresh,
      onAuthFailure: vi.fn(),
    });

    await expect(client.request("/api/v1/categories")).rejects.toMatchObject({
      status: 401,
      code: "not_authenticated",
    });
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it.each([
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/logout",
    "/api/v1/auth/refresh",
  ])("never auto-refreshes the auth session endpoint %s", async (path) => {
    const refresh = vi.fn();
    const fetchMock = vi.fn().mockResolvedValue(
      authError(401, "invalid_credentials", "Sensitive backend detail"),
    );
    const client = createApiClient({
      fetch: fetchMock,
      getAccessToken: () => "access-token",
      refresh,
      onAuthFailure: vi.fn(),
    });

    await expect(
      client.request(path, { method: "POST", authMode: "protected" }),
    ).rejects.toBeInstanceOf(ApiError);
    expect(refresh).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("clears auth state without retrying when refresh fails", async () => {
    const clearAuth = vi.fn();
    const fetchMock = vi.fn().mockResolvedValue(
      authError(401, "not_authenticated", "Authentication is required."),
    );
    const client = createApiClient({
      fetch: fetchMock,
      getAccessToken: () => "expired-token",
      refresh: vi.fn().mockRejectedValue(new Error("session expired")),
      onAuthFailure: clearAuth,
    });

    await expect(client.request("/api/v1/categories")).rejects.toBeInstanceOf(ApiError);
    expect(clearAuth).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

describe("auth shell", () => {
  it("waits for the single startup refresh before resolving a protected route", async () => {
    let finishRefresh: ((value: Response) => void) | undefined;
    const pendingRefresh = new Promise<Response>((resolve) => {
      finishRefresh = resolve;
    });
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const path = requestPath(input);
      if (path === "/api/v1/auth/refresh") return pendingRefresh;
      if (path.startsWith("/api/v1/events/timeline")) return Promise.resolve(response(200, { items: [] }));
      if (path === "/api/v1/categories") return Promise.resolve(response(200, []));
      return Promise.resolve(response(404));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderApp();

    expect(screen.getByRole("status")).toHaveTextContent("Restoring session");
    expect(screen.queryByRole("heading", { name: "Your Pawprints" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Welcome back" })).not.toBeInTheDocument();

    await act(async () => finishRefresh?.(response(200, session)));

    expect(await screen.findByRole("heading", { name: "Your Pawprints" })).toBeInTheDocument();
    const refreshCalls = fetchMock.mock.calls.filter(
      ([input]) => requestPath(input) === "/api/v1/auth/refresh",
    );
    expect(refreshCalls).toHaveLength(1);
    expect(refreshCalls[0]).toEqual([
      "/api/v1/auth/refresh",
      expect.objectContaining({ method: "POST", credentials: "include" }),
    ]);
  });

  it("redirects protected navigation to login when startup refresh fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        authError(401, "invalid_refresh_token", "Refresh session is invalid."),
      ),
    );

    renderApp("/");

    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
  });

  it("logs in, keeps the access token out of browser storage, and uses it for API calls", async () => {
    const storageWrite = vi.spyOn(Storage.prototype, "setItem");
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const path = requestPath(input);
      if (path.endsWith("/refresh")) {
        return authError(401, "invalid_refresh_token", "Refresh session is invalid.");
      }
      if (path.endsWith("/login")) return response(200, session);
      if (path === "/api/v1/categories") return response(200, []);
      return response(404);
    });
    vi.stubGlobal("fetch", fetchMock);
    const browserUser = userEvent.setup();
    renderApp("/login");
    await screen.findByRole("heading", { name: "Welcome back" });

    await browserUser.type(screen.getByLabelText("Email"), "sam@example.com");
    await browserUser.type(screen.getByLabelText("Password"), "correct horse battery");
    await browserUser.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("heading", { name: "Your Pawprints" })).toBeInTheDocument();
    await act(async () => {
      await apiRequest("/api/v1/categories");
    });
    const categoryCall = fetchMock.mock.calls.find(([input]) => requestPath(input) === "/api/v1/categories");
    expect(new Headers(categoryCall?.[1]?.headers).get("Authorization")).toBe(
      "Bearer runtime-access-token",
    );
    expect(storageWrite).not.toHaveBeenCalled();
    expect(window.localStorage).toHaveLength(0);
    expect(window.sessionStorage).toHaveLength(0);
  });

  it("shows a generic login error without leaking backend detail", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) =>
      requestPath(input).endsWith("/refresh")
        ? authError(401, "invalid_refresh_token", "Refresh session is invalid.")
        : authError(401, "invalid_credentials", "Database lookup for sam@example.com failed"),
    );
    vi.stubGlobal("fetch", fetchMock);
    const browserUser = userEvent.setup();
    renderApp("/login");
    await screen.findByRole("heading", { name: "Welcome back" });

    await browserUser.type(screen.getByLabelText("Email"), "sam@example.com");
    await browserUser.type(screen.getByLabelText("Password"), "wrong password");
    await browserUser.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password.");
    expect(screen.getByRole("alert")).not.toHaveTextContent("Database");
    expect(screen.getByRole("button", { name: "Sign in" })).toBeEnabled();
  });

  it("registers with the backend contract and enters the protected shell", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, _init?: RequestInit) =>
      requestPath(input).endsWith("/refresh")
        ? authError(401, "invalid_refresh_token", "Refresh session is invalid.")
        : response(201, session),
    );
    vi.stubGlobal("fetch", fetchMock);
    const browserUser = userEvent.setup();
    renderApp("/register");
    await screen.findByRole("heading", { name: "Create your account" });

    await browserUser.type(screen.getByLabelText("Display name (optional)"), "Sam");
    await browserUser.type(screen.getByLabelText("Email"), "sam@example.com");
    await browserUser.type(screen.getByLabelText("Password"), "correct horse battery");
    await browserUser.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("heading", { name: "Your Pawprints" })).toBeInTheDocument();
    const registerCall = fetchMock.mock.calls.find(([input]) => requestPath(input).endsWith("/register"));
    expect(JSON.parse(String(registerCall?.[1]?.body))).toEqual({
      display_name: "Sam",
      email: "sam@example.com",
      password: "correct horse battery",
    });
  });

  it("keeps register password validation aligned with the backend six-character minimum", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        authError(401, "invalid_refresh_token", "Refresh session is invalid."),
      ),
    );
    renderApp("/register");
    await screen.findByRole("heading", { name: "Create your account" });

    const password = screen.getByLabelText("Password");
    expect(password).toHaveAttribute("minLength", "6");
    expect(password).toHaveAttribute("maxLength", "128");
    expect(screen.getByText("Use 6 to 128 characters.")).toBeInTheDocument();
  });

  it("surfaces safe registration errors and restores the enabled form", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) =>
      requestPath(input).endsWith("/refresh")
        ? authError(401, "invalid_refresh_token", "Refresh session is invalid.")
        : authError(409, "email_already_registered", "Internal duplicate key detail"),
    );
    vi.stubGlobal("fetch", fetchMock);
    const browserUser = userEvent.setup();
    renderApp("/register");
    await screen.findByRole("heading", { name: "Create your account" });

    await browserUser.type(screen.getByLabelText("Email"), "sam@example.com");
    await browserUser.type(screen.getByLabelText("Password"), "correct horse battery");
    await browserUser.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "An account with this email already exists.",
    );
    expect(screen.getByRole("alert")).not.toHaveTextContent("duplicate key");
    expect(screen.getByRole("button", { name: "Create account" })).toBeEnabled();
  });

  it("clears an established session and redirects when business-request refresh fails", async () => {
    let protectedCalls = 0;
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const path = requestPath(input);
      if (path.endsWith("/refresh") && protectedCalls === 0) return response(200, session);
      if (path.startsWith("/api/v1/events/timeline")) return response(200, { items: [] });
      if (path === "/api/v1/categories") return response(200, []);
      if (path === "/api/v1/events/search?keyword=run") {
        protectedCalls += 1;
        return authError(401, "not_authenticated", "Authentication is required.");
      }
      return authError(401, "invalid_refresh_token", "Refresh session is invalid.");
    });
    vi.stubGlobal("fetch", fetchMock);
    renderApp();
    await screen.findByRole("heading", { name: "Your Pawprints" });

    await act(async () => {
      await expect(apiRequest("/api/v1/events/search?keyword=run")).rejects.toBeInstanceOf(
        ApiError,
      );
    });

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
    });
    expect(protectedCalls).toBe(1);
  });
});

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { configureApiClient, createApiClient } from "../api/client";

export interface AuthUser {
  id: string;
  email: string;
  display_name: string | null;
}

interface AuthSession {
  access_token: string;
  token_type: "Bearer";
  expires_in: number;
  user: AuthUser;
}

interface RegisterInput {
  email: string;
  password: string;
  display_name: string | null;
}

interface AuthContextValue {
  accessToken: string | null;
  user: AuthUser | null;
  isRestoring: boolean;
  login(email: string, password: string): Promise<void>;
  register(input: RegisterInput): Promise<void>;
  logout(): Promise<void>;
  refresh(): Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isRestoring, setIsRestoring] = useState(true);
  const accessTokenRef = useRef<string | null>(null);
  const refreshInFlight = useRef<Promise<void> | null>(null);
  const startupRefresh = useRef<Promise<void> | null>(null);

  const applySession = useCallback((session: AuthSession) => {
    accessTokenRef.current = session.access_token;
    setAccessToken(session.access_token);
    setUser(session.user);
  }, []);

  const clearSession = useCallback(() => {
    accessTokenRef.current = null;
    setAccessToken(null);
    setUser(null);
  }, []);

  const sessionClient = useMemo(
    () =>
      createApiClient({
        getAccessToken: () => null,
        refresh: () => Promise.reject(new Error("Session endpoints cannot refresh themselves.")),
        onAuthFailure: clearSession,
      }),
    [clearSession],
  );

  const refresh = useCallback(() => {
    if (!refreshInFlight.current) {
      const attempt = sessionClient
        .request<AuthSession>("/api/v1/auth/refresh", {
          method: "POST",
          authMode: "session",
        })
        .then(({ data }) => applySession(data))
        .catch((error: unknown) => {
          clearSession();
          throw error;
        })
        .finally(() => {
          if (refreshInFlight.current === attempt) refreshInFlight.current = null;
        });
      refreshInFlight.current = attempt;
    }
    return refreshInFlight.current;
  }, [applySession, clearSession, sessionClient]);

  const apiClient = useMemo(
    () =>
      createApiClient({
        getAccessToken: () => accessTokenRef.current,
        refresh,
        onAuthFailure: clearSession,
      }),
    [clearSession, refresh],
  );

  useEffect(() => configureApiClient(apiClient), [apiClient]);

  useEffect(() => {
    let active = true;
    if (!startupRefresh.current) startupRefresh.current = refresh();
    startupRefresh.current.catch(() => undefined).finally(() => {
      if (active) setIsRestoring(false);
    });
    return () => {
      active = false;
    };
  }, [refresh]);

  const login = useCallback(
    async (email: string, password: string) => {
      const { data } = await sessionClient.request<AuthSession>("/api/v1/auth/login", {
        method: "POST",
        authMode: "session",
        body: JSON.stringify({ email, password }),
      });
      applySession(data);
    },
    [applySession, sessionClient],
  );

  const register = useCallback(
    async (input: RegisterInput) => {
      const { data } = await sessionClient.request<AuthSession>("/api/v1/auth/register", {
        method: "POST",
        authMode: "session",
        body: JSON.stringify(input),
      });
      applySession(data);
    },
    [applySession, sessionClient],
  );

  const logout = useCallback(async () => {
    try {
      await sessionClient.request<void>("/api/v1/auth/logout", {
        method: "POST",
        authMode: "session",
      });
    } finally {
      clearSession();
    }
  }, [clearSession, sessionClient]);

  const value = useMemo(
    () => ({ accessToken, user, isRestoring, login, register, logout, refresh }),
    [accessToken, isRestoring, login, logout, refresh, register, user],
  );

  if (isRestoring) {
    return (
      <main className="session-loading" role="status" aria-live="polite">
        <span className="brand-mark" aria-hidden="true">P</span>
        <span>Restoring session...</span>
      </main>
    );
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider.");
  return context;
}

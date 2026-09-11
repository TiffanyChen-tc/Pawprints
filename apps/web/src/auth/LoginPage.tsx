import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { useAuth } from "./AuthProvider";

function safeLoginError(error: unknown) {
  if (error instanceof ApiError && error.code === "invalid_credentials") {
    return "Invalid email or password.";
  }
  return "We could not sign you in. Please try again.";
}

export default function LoginPage() {
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (user) return <Navigate to="/" replace />;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    const data = new FormData(event.currentTarget);
    try {
      await login(String(data.get("email")), String(data.get("password")));
      const destination = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname;
      navigate(destination?.startsWith("/") ? destination : "/", { replace: true });
    } catch (caught) {
      setError(safeLoginError(caught));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="auth-layout">
      <section className="auth-intro" aria-labelledby="login-title">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true">P</span>
          <span>Pawprints</span>
        </div>
        <div>
          <p className="eyebrow">Your days, remembered</p>
          <h1 id="login-title">Welcome back</h1>
          <p className="auth-copy">Sign in to return to the moments you have been collecting.</p>
        </div>
      </section>
      <section className="auth-form-panel" aria-label="Sign in">
        <form onSubmit={submit}>
          <label htmlFor="login-email">Email</label>
          <input id="login-email" name="email" type="email" autoComplete="email" required />
          <label htmlFor="login-password">Password</label>
          <input id="login-password" name="password" type="password" autoComplete="current-password" required />
          {error && <p className="form-error" role="alert">{error}</p>}
          <button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Signing in..." : "Sign in"}
          </button>
        </form>
        <p className="auth-switch">New to Pawprints? <Link to="/register">Create an account</Link></p>
      </section>
    </main>
  );
}

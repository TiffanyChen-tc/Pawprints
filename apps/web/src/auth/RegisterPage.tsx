import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";

import { ApiError } from "../api/client";
import { useAuth } from "./AuthProvider";

function safeRegisterError(error: unknown) {
  if (error instanceof ApiError && error.code === "email_already_registered") {
    return "An account with this email already exists.";
  }
  if (error instanceof ApiError && error.code === "validation_failed") {
    return "Check your email and password, then try again.";
  }
  return "We could not create your account. Please try again.";
}

export default function RegisterPage() {
  const { register, user } = useAuth();
  const navigate = useNavigate();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (user) return <Navigate to="/" replace />;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    const data = new FormData(event.currentTarget);
    const displayName = String(data.get("display_name")).trim();
    try {
      await register({
        display_name: displayName || null,
        email: String(data.get("email")),
        password: String(data.get("password")),
      });
      navigate("/", { replace: true });
    } catch (caught) {
      setError(safeRegisterError(caught));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="auth-layout">
      <section className="auth-intro" aria-labelledby="register-title">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true">P</span>
          <span>Pawprints</span>
        </div>
        <div>
          <p className="eyebrow">Begin your record</p>
          <h1 id="register-title">Create your account</h1>
          <p className="auth-copy">A private place for the small moments that make up a life.</p>
        </div>
      </section>
      <section className="auth-form-panel" aria-label="Create account">
        <form onSubmit={submit}>
          <label htmlFor="register-name">Display name (optional)</label>
          <input id="register-name" name="display_name" type="text" autoComplete="name" />
          <label htmlFor="register-email">Email</label>
          <input id="register-email" name="email" type="email" autoComplete="email" required />
          <label htmlFor="register-password">Password</label>
          <input
            id="register-password"
            name="password"
            type="password"
            autoComplete="new-password"
            minLength={6}
            maxLength={128}
            aria-describedby="password-hint"
            required
          />
          <p className="field-hint" id="password-hint">Use 6 to 128 characters.</p>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Creating account..." : "Create account"}
          </button>
        </form>
        <p className="auth-switch">Already have an account? <Link to="/login">Sign in</Link></p>
      </section>
    </main>
  );
}

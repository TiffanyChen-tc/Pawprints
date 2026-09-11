import { LogOut } from "lucide-react";
import { Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "./auth/AuthProvider";
import LoginPage from "./auth/LoginPage";
import ProtectedRoute from "./auth/ProtectedRoute";
import RegisterPage from "./auth/RegisterPage";

function AppShell() {
  const { logout, user } = useAuth();

  return (
    <main className="app-shell">
      <header className="app-header">
        <div className="brand-lockup">
          <span className="brand-mark" aria-hidden="true">P</span>
          <span>Pawprints</span>
        </div>
        <div className="account-controls">
          <span>{user?.display_name || user?.email}</span>
          <button className="icon-button" type="button" onClick={() => void logout()} title="Sign out" aria-label="Sign out">
            <LogOut aria-hidden="true" size={18} />
          </button>
        </div>
      </header>
      <section className="placeholder-view">
        <p className="eyebrow">Private journal</p>
        <h1>Your Pawprints</h1>
        <p>Your daily timeline will appear here.</p>
      </section>
    </main>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/" element={<AppShell />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

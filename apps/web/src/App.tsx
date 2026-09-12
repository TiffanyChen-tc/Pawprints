import { BarChart3, CalendarDays, LogOut, Search } from "lucide-react";
import { NavLink, Navigate, Outlet, Route, Routes } from "react-router-dom";

import AnalyticsPage from "./analytics/AnalyticsPage";
import { useAuth } from "./auth/AuthProvider";
import LoginPage from "./auth/LoginPage";
import ProtectedRoute from "./auth/ProtectedRoute";
import RegisterPage from "./auth/RegisterPage";
import TimelinePage from "./events/TimelinePage";
import SearchPage from "./search/SearchPage";

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
      <nav className="app-nav" aria-label="Journal navigation"><NavLink to="/timeline"><CalendarDays aria-hidden="true" size={16} /> Timeline</NavLink><NavLink to="/search"><Search aria-hidden="true" size={16} /> Search</NavLink><NavLink to="/analytics"><BarChart3 aria-hidden="true" size={16} /> Analytics</NavLink></nav>
      <Outlet />
    </main>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route element={<ProtectedRoute />}>
        <Route path="/" element={<Navigate to="/timeline" replace />} />
        <Route element={<AppShell />}>
          <Route path="/timeline" element={<TimelinePage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import CentralBooksLoginPage from "./LoginPage";
import "../index.css";

/**
 * Option B Login Entry
 * Fetches config from /api/auth/config instead of reading from DOM.
 */

interface AuthConfig {
  csrfToken: string;
  googleEnabled: boolean;
  googleLoginUrl: string | null;
  nextUrl: string;
  loginUrl: string;
}

function LoginApp() {
  const [config, setConfig] = useState<AuthConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Get next URL from query string
    const params = new URLSearchParams(window.location.search);
    const nextParam = params.get("next") || "";

    fetch(`/api/auth/config${nextParam ? `?next=${encodeURIComponent(nextParam)}` : ""}`)
      .then(async (res) => {
        if (!res.ok) {
          throw new Error("Failed to load login configuration");
        }
        const data = await res.json();
        setConfig(data);
      })
      .catch((err) => {
        console.error("[LoginApp] Failed to fetch config:", err);
        setError(err.message || "Failed to load login page");
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-slate-400 text-sm">Loading...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="text-rose-600 text-sm">{error}</div>
      </div>
    );
  }

  return (
    <CentralBooksLoginPage
      action="/login/"
      csrfToken={config?.csrfToken}
      nextUrl={config?.nextUrl}
      googleEnabled={config?.googleEnabled}
      googleLoginUrl={config?.googleLoginUrl}
    />
  );
}

document.addEventListener("DOMContentLoaded", () => {
  const container = document.getElementById("login-root");
  if (!container) {
    return;
  }

  const root = createRoot(container);
  root.render(<LoginApp />);

  window.dispatchEvent(new Event("login-app-mounted"));
});

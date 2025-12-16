import "../index.css";
import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import CloverBooksDashboard, { type CloverBooksDashboardProps } from "./CloverBooksDashboard";
import CloverBooksWelcomeOnboarding from "./CloverBooksWelcomeOnboarding";
import { AuthProvider } from "../contexts/AuthContext";

const router = {
  push: (href: string) => {
    if (!href) return;
    window.location.href = href;
  },
};

/**
 * Wrapper component that fetches dashboard data from API (Option B architecture).
 */
const DashboardApp: React.FC = () => {
  const [payload, setPayload] = useState<CloverBooksDashboardProps | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchDashboard = async () => {
      try {
        // Preserve any query params (e.g., pl_period_preset) when fetching
        const queryString = window.location.search;
        const res = await fetch(`/api/dashboard/${queryString}`);

        if (!res.ok) {
          const errorData = await res.json().catch(() => ({}));
          throw new Error(errorData.error || `HTTP ${res.status}`);
        }

        const data = await res.json();
        setPayload(data);
        setError(null);
      } catch (err: any) {
        console.error("Failed to load dashboard:", err);
        setError(err?.message || "Failed to load dashboard");
      } finally {
        setLoading(false);
      }
    };

    fetchDashboard();
  }, []);

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50">
        <div className="max-w-7xl mx-auto px-6 py-12">
          <div className="animate-pulse space-y-6">
            <div className="h-8 w-48 bg-slate-200 rounded" />
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-32 bg-slate-200 rounded-xl" />
              ))}
            </div>
            <div className="h-64 bg-slate-200 rounded-xl" />
          </div>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="min-h-screen bg-slate-50">
        <div className="max-w-2xl mx-auto px-6 py-12">
          <div className="bg-red-50 border border-red-200 rounded-xl p-6">
            <h2 className="text-lg font-semibold text-red-800 mb-2">Unable to load dashboard</h2>
            <p className="text-red-700 text-sm">{error}</p>
            <button
              onClick={() => window.location.reload()}
              className="mt-4 px-4 py-2 bg-red-600 text-white text-sm font-medium rounded-lg hover:bg-red-700"
            >
              Try again
            </button>
          </div>
        </div>
      </div>
    );
  }

  // No data (shouldn't happen but defensive)
  if (!payload) {
    return null;
  }

  const startBooksUrl = payload.urls?.startBooks || "/customers/new/";
  const bankImportUrl = payload.urls?.bankImport || "/bank/import/";

  // Render appropriate component based on workspace state
  if (payload.is_empty_workspace) {
    return (
      <CloverBooksWelcomeOnboarding
        onStartBooks={() => router.push(startBooksUrl)}
        onUploadSampleCsv={() => router.push(bankImportUrl)}
      />
    );
  }

  return <CloverBooksDashboard {...payload} />;
};

// Mount the app
const rootEl = document.getElementById("dashboard-root");

if (rootEl) {
  const root = createRoot(rootEl);
  root.render(
    <AuthProvider>
      <DashboardApp />
    </AuthProvider>
  );
  window.dispatchEvent(new Event("dashboard-mounted"));
}

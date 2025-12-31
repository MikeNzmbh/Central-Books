import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate, useSearchParams } from "react-router-dom";
import "../setup";
import { AuthProvider } from "../contexts/AuthContext";
import CompanionControlTowerPage from "./CompanionControlTowerPage";
import TaxGuardianPage from "./TaxGuardianPage";
import TaxSettingsPage from "./TaxSettingsPage";
import TaxProductRulesPage from "./TaxProductRulesPage";
import TaxCatalogPage from "./TaxCatalogPage";
import PanelShell from "./PanelShell";
import SuggestionsPanel from "./SuggestionsPanel";
import IssuesPanel from "./IssuesPanel";
import CloseAssistantDrawer from "./CloseAssistantDrawer";
import { PanelType } from "./companionCopy";

const rootEl = document.getElementById("companion-overview-root");

// ─────────────────────────────────────────────────────────────────────────────
// Panel Router Wrapper
// ─────────────────────────────────────────────────────────────────────────────

/**
 * The new CompanionControlTowerPage has its own built-in panel system.
 * It reads query params internally (e.g., ?panel=suggestions).
 */
const ControlTowerWithPanels: React.FC = () => {
  return <CompanionControlTowerPage />;
};

// ─────────────────────────────────────────────────────────────────────────────
// Legacy Redirect Component
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Redirect legacy routes to new panel-based routes.
 */
const LegacyRedirect: React.FC<{ panel: PanelType }> = ({ panel }) => {
  return <Navigate to={`/?panel=${panel}`} replace />;
};

// ─────────────────────────────────────────────────────────────────────────────
// Error Boundary
// ─────────────────────────────────────────────────────────────────────────────

class ErrorBoundary extends React.Component<{ children: React.ReactNode }, { hasError: boolean; message: string }> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, message: "" };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, message: error?.message || "Something went wrong" };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("Companion Control Tower crashed:", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
          <div className="max-w-md w-full bg-white border border-slate-200 rounded-xl shadow-sm p-4 text-center">
            <h1 className="text-lg font-semibold text-slate-900">Companion Control Tower failed to load</h1>
            <p className="text-sm text-slate-600 mt-2">{this.state.message}</p>
            <p className="text-xs text-slate-400 mt-2">Check the browser console for details.</p>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Mount Application
// ─────────────────────────────────────────────────────────────────────────────

if (rootEl) {
  const root = createRoot(rootEl);
  root.render(
    <React.StrictMode>
      <ErrorBoundary>
        <AuthProvider>
          <BrowserRouter basename="/ai-companion">
            <Routes>
              {/* Main Control Tower with panel support */}
              <Route path="/" element={<ControlTowerWithPanels />} />

              {/* Legacy redirects → panel routes */}
              <Route path="/shadow-ledger" element={<LegacyRedirect panel="suggestions" />} />
              <Route path="/shadow-ledger/review" element={<LegacyRedirect panel="suggestions" />} />
              <Route path="/shadow-ledger-proposals" element={<LegacyRedirect panel="suggestions" />} />
              <Route path="/proposals" element={<LegacyRedirect panel="suggestions" />} />
              <Route path="/issues" element={<LegacyRedirect panel="issues" />} />
              <Route path="/close" element={<LegacyRedirect panel="close" />} />

              {/* Tax Guardian (separate pages - justified) */}
              <Route path="/tax" element={<TaxGuardianPage />} />
              <Route path="/tax/settings" element={<TaxSettingsPage />} />
              <Route path="/tax/product-rules" element={<TaxProductRulesPage />} />
              <Route path="/tax/catalog" element={<TaxCatalogPage />} />
            </Routes>
          </BrowserRouter>
        </AuthProvider>
      </ErrorBoundary>
    </React.StrictMode>
  );
} else {
  console.warn("Companion Control Tower root element not found");
}

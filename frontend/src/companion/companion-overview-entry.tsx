import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import "../index.css";
import { AuthProvider } from "../contexts/AuthContext";
import CompanionOverviewPage from "./CompanionOverviewPage";
import CompanionProposalsPage from "./CompanionProposalsPage";
import TaxGuardianPage from "./TaxGuardianPage";
import TaxSettingsPage from "./TaxSettingsPage";
import TaxProductRulesPage from "./TaxProductRulesPage";
import TaxCatalogPage from "./TaxCatalogPage";

const rootEl = document.getElementById("companion-overview-root");

class ErrorBoundary extends React.Component<{ children: React.ReactNode }, { hasError: boolean; message: string }> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, message: "" };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, message: error?.message || "Something went wrong" };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    // Log for troubleshooting; avoids silent blank screen.
    console.error("CompanionOverviewPage crashed:", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
          <div className="max-w-md w-full bg-white border border-slate-200 rounded-xl shadow-sm p-4 text-center">
            <h1 className="text-lg font-semibold text-slate-900">AI Companion failed to load</h1>
            <p className="text-sm text-slate-600 mt-2">{this.state.message}</p>
            <p className="text-xs text-slate-400 mt-2">Check the browser console for details.</p>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

if (rootEl) {
  const root = createRoot(rootEl);
  root.render(
    <React.StrictMode>
      <ErrorBoundary>
        <AuthProvider>
          <BrowserRouter basename="/ai-companion">
            <Routes>
              <Route path="/" element={<CompanionOverviewPage />} />
              <Route path="/proposals" element={<CompanionProposalsPage />} />
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
  console.warn("Companion overview root not found");
}

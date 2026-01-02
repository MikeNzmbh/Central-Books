import React from "react";
import { createRoot } from "react-dom/client";
import ReconciliationPage from "./ReconciliationPage";
import "../setup";
import { AuthProvider } from "../contexts/AuthContext";
import { ToastProvider } from "../contexts/ToastContext";

const rootEl = document.getElementById("reconciliation-root");

if (!rootEl) {
  console.warn("Reconciliation root element not found; app not mounted.");
} else {
  const bankAccountId = rootEl.dataset?.bankAccountId || "";
  const root = createRoot(rootEl);

  root.render(
    <React.StrictMode>
      <AuthProvider>
        <ToastProvider>
          <ReconciliationPage bankAccountId={bankAccountId} />
        </ToastProvider>
      </AuthProvider>
    </React.StrictMode>
  );

  window.dispatchEvent(new Event("reconciliation-app-mounted"));
}

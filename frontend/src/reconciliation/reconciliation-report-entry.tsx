// frontend/src/reconciliation/reconciliation-report-entry.tsx
import React from "react";
import ReactDOM from "react-dom/client";
import ReconciliationReportPage from "./ReconciliationReportPage";
import "../index.css";

const rootEl = document.getElementById("reconciliation-report-root");
if (!rootEl) {
    throw new Error("Reconciliation report root element not found");
}

const sessionId = rootEl.dataset.sessionId || "";

const root = ReactDOM.createRoot(rootEl);
root.render(
    <React.StrictMode>
        <ReconciliationReportPage sessionId={sessionId} />
    </React.StrictMode>
);

window.dispatchEvent(new Event("reconciliation-report-mounted"));

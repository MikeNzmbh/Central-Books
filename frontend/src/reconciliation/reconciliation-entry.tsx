import React from "react";
import ReactDOM from "react-dom/client";
import ReconciliationPage from "./ReconciliationPage";
import "../index.css";

const rootEl = document.getElementById("reconciliation-root");
if (!rootEl) {
  throw new Error("Reconciliation root element not found");
}

const bankAccountId = rootEl.dataset.bankAccountId || "";

const root = ReactDOM.createRoot(rootEl);
root.render(
  <React.StrictMode>
    <ReconciliationPage bankAccountId={bankAccountId} />
  </React.StrictMode>
);

window.dispatchEvent(new Event("reconciliation-app-mounted"));

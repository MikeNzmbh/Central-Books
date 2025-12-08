import React from "react";
import { createRoot } from "react-dom/client";
import "../index.css";
import BankAuditHealthCheckPage from "./BankReviewPage";

const rootEl = document.getElementById("bank-review-root");

if (rootEl) {
  const root = createRoot(rootEl);
  root.render(
    <React.StrictMode>
      <BankAuditHealthCheckPage />
    </React.StrictMode>
  );
} else {
  console.warn("Bank audit health check root not found");
}

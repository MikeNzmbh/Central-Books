import React from "react";
import { createRoot } from "react-dom/client";
import "../index.css";
import InvoicesPage from "./InvoicesPage";

const rootEl = document.getElementById("invoices-root");

if (rootEl) {
  const defaultCurrency = rootEl.dataset.defaultCurrency || "USD";
  const root = createRoot(rootEl);
  root.render(
    <React.StrictMode>
      <InvoicesPage defaultCurrency={defaultCurrency} />
    </React.StrictMode>
  );
} else {
  console.warn("Invoices root not found");
}

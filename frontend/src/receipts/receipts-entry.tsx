import React from "react";
import { createRoot } from "react-dom/client";
import "../index.css";
import ReceiptsPage from "./ReceiptsPage";

const rootEl = document.getElementById("receipts-root");

if (rootEl) {
  const defaultCurrency = rootEl.dataset.defaultCurrency || "USD";
  const root = createRoot(rootEl);
  root.render(
    <React.StrictMode>
      <ReceiptsPage defaultCurrency={defaultCurrency} />
    </React.StrictMode>
  );
} else {
  console.warn("Receipts root not found");
}

import React from "react";
import { createRoot } from "react-dom/client";
import "../index.css";
import BankReviewPage from "./BankReviewPage";

const rootEl = document.getElementById("bank-review-root");

if (rootEl) {
  const root = createRoot(rootEl);
  root.render(
    <React.StrictMode>
      <BankReviewPage />
    </React.StrictMode>
  );
} else {
  console.warn("Bank review root not found");
}

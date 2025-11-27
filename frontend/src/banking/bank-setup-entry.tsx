import React from "react";
import ReactDOM from "react-dom/client";
import BankSetupPage from "./BankSetupPage";
import "../index.css";

const rootEl = document.getElementById("bank-setup-root");

if (!rootEl) {
  throw new Error("Bank setup root element not found");
}

const skipUrl = rootEl.getAttribute("data-skip-url") || undefined;

ReactDOM.createRoot(rootEl).render(
  <React.StrictMode>
    <BankSetupPage skipUrl={skipUrl} />
  </React.StrictMode>
);

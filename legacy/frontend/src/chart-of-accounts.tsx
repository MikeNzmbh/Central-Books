import React from "react";
import { createRoot } from "react-dom/client";
import ChartOfAccountsPage, { ChartOfAccountsBootPayload } from "./ChartOfAccountsPage";
import "./setup";

const el = document.getElementById("chart-of-accounts-root");
const dataEl = document.getElementById("chart-of-accounts-data");

if (el) {
  const newAccountUrl = el.getAttribute("data-new-account-url") || "";
  const initialJson =
    (dataEl && dataEl.textContent) || el.getAttribute("data-initial") || "{}";

  let payload: ChartOfAccountsBootPayload = {
    accounts: [],
    currencyCode: "USD",
  };
  try {
    const parsed = JSON.parse(initialJson);
    payload = {
      accounts: parsed.accounts || [],
      currencyCode: parsed.currencyCode || "USD",
      totalsByType: parsed.totalsByType || {},
    };
  } catch (err) {
    if (window.console) {
      console.error("Unable to parse Chart of Accounts payload:", err);
    }
  }

  const root = createRoot(el);
  root.render(
    <React.StrictMode>
      <ChartOfAccountsPage payload={payload} newAccountUrl={newAccountUrl} />
    </React.StrictMode>
  );
}

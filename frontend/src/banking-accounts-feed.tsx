import React from "react";
import ReactDOM from "react-dom/client";
import "./setup";
import BankingAccountsAndFeedPage from "./BankingAccountsAndFeedPage";
import { AuthProvider } from "./contexts/AuthContext";

const rootEl = document.getElementById("banking-root") as HTMLElement | null;

if (rootEl) {
  const overviewUrl = rootEl.dataset.overviewUrl || "/api/banking/overview/";
  const feedUrl = rootEl.dataset.feedUrl || "/bank-feeds/";
  const importUrl = rootEl.dataset.importUrl || "/bank-feeds/new/";

  ReactDOM.createRoot(rootEl).render(
    <React.StrictMode>
      <AuthProvider>
        <BankingAccountsAndFeedPage overviewUrl={overviewUrl} feedUrl={feedUrl} importUrl={importUrl} />
      </AuthProvider>
    </React.StrictMode>
  );
}

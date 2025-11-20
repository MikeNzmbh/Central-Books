import React from "react";
import { createRoot } from "react-dom/client";
import CentralBooksDashboard, { type CentralBooksDashboardProps } from "./CentralBooksDashboard";
import CentralBooksWelcomeOnboarding from "./CentralBooksWelcomeOnboarding";
import "../index.css";

const router = {
  push: (href: string) => {
    if (!href) return;
    window.location.href = href;
  },
};

const rootEl = document.getElementById("dashboard-root");
const dataEl = document.getElementById("dashboard-data");

if (rootEl && dataEl) {
  try {
    const payload = JSON.parse(dataEl.textContent || "{}") as CentralBooksDashboardProps;
    const startBooksUrl = payload.urls?.startBooks || "/customers/new/";
    const bankImportUrl = payload.urls?.bankImport || "/bank/import/";
    const root = createRoot(rootEl);
    root.render(
      payload.is_empty_workspace ? (
        <CentralBooksWelcomeOnboarding
          onStartBooks={() => router.push(startBooksUrl)}
          onUploadSampleCsv={() => router.push(bankImportUrl)}
        />
      ) : (
        <CentralBooksDashboard {...payload} />
      )
    );
    window.dispatchEvent(new Event("dashboard-mounted"));
  } catch (error) {
    console.error("Unable to parse dashboard payload", error);
  }
}

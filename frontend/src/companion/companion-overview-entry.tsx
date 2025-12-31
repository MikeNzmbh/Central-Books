import React from "react";
import { createRoot } from "react-dom/client";
import "../index.css";
import CompanionOverviewPage from "./CompanionOverviewPage";

const rootEl = document.getElementById("companion-overview-root");

if (rootEl) {
  const root = createRoot(rootEl);
  root.render(
    <React.StrictMode>
      <CompanionOverviewPage />
    </React.StrictMode>
  );
} else {
  console.warn("Companion overview root not found");
}
